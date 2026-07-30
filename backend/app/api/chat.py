"""
对话 API — SSE 流式输出

核心接口:
  POST /api/chat            — 流式对话
  GET  /api/conversations   — 对话列表

SSE (Server-Sent Events) 原理（面试必考）:
  1. 服务端设置 Content-Type: text/event-stream
  2. 每发送一个数据块，格式为 "data: {json}\n\n"
  3. 客户端通过 EventSource 或 httpx 逐条读取
  4. 相比 WebSocket: SSE 是单向（服务器→客户端），更简单，无需握手
  5. 为什么不用 WebSocket?
     → 对话场景只需要服务器推送，客户端请求走 HTTP 即可
     → SSE 天然支持 HTTP/2 多路复用，浏览器原生支持自动重连
"""

import json
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.llm import llm_service
from app.core.memory import ConversationMemory
from app.database import get_db
from app.models.conversation import Conversation
from app.models.message import Message

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["chat"])

# 内存中的记忆管理器字典 {conversation_id: ConversationMemory}
# 注意: 生产环境应该用 Redis
_memories: dict[int, ConversationMemory] = {}


# ============================================================
# Pydantic Schema
# ============================================================

class ChatRequest(BaseModel):
    """对话请求"""
    conversation_id: int | None = Field(
        default=None, description="对话ID，为空则创建新对话"
    )
    message: str = Field(..., min_length=1, max_length=10000, description="用户消息")
    system_prompt: str | None = Field(
        default=None, description="系统提示词（可选）"
    )


class ConversationCreate(BaseModel):
    """创建对话请求"""
    title: str = Field(default="新对话", max_length=200)


# ============================================================
# 辅助函数
# ============================================================

def _get_or_create_memory(conv_id: int) -> ConversationMemory:
    """获取或创建对话记忆"""
    if conv_id not in _memories:
        _memories[conv_id] = ConversationMemory(max_turns=10)
    return _memories[conv_id]


def _build_system_prompt() -> str:
    """构建默认的系统提示词"""
    return (
        "你是一个专业的AI知识助手，名为「AI Second Brain」。\n"
        "你的职责是帮助用户管理知识、回答问题、整理思路。\n\n"
        "你的回答风格：\n"
        "- 专业但易懂，用简洁的语言解释复杂概念\n"
        "- 使用 Markdown 格式，合理使用标题、列表、代码块\n"
        "- 如果用户提供文档内容，优先基于文档回答\n"
        "- 如果不确定，诚实说明，不要编造\n\n"
        "当前时间: " + datetime.now().strftime("%Y-%m-%d %H:%M")
    )


# ============================================================
# API 端点
# ============================================================

@router.post("/chat")
async def chat(request: ChatRequest, db: Session = Depends(get_db)):
    """
    流式对话接口

    返回 SSE 事件流:
      data: {"type": "token", "content": "你"}
      data: {"type": "token", "content": "好"}
      ...
      data: {"type": "done", "message_id": 42, "tokens": 156}

    流程:
      1. 接收用户消息
      2. 获取/创建对话和记忆
      3. 构建 Prompt → 调 LLM 流式生成
      4. 实时推送 token → 保存完整回复到数据库
    """

    # 1. 处理对话
    conversation = None
    if request.conversation_id:
        conversation = db.query(Conversation).filter_by(
            id=request.conversation_id
        ).first()
        if not conversation:
            raise HTTPException(status_code=404, detail="对话不存在")

    if not conversation:
        # 用用户消息的前30个字作为标题
        title = request.message[:30] + ("..." if len(request.message) > 30 else "")
        conversation = Conversation(title=title)
        db.add(conversation)
        db.commit()
        db.refresh(conversation)

    # 2. 保存用户消息
    user_msg = Message(
        conversation_id=conversation.id,
        role="user",
        content=request.message,
    )
    db.add(user_msg)
    db.commit()

    # 3. 获取记忆管理器
    memory = _get_or_create_memory(conversation.id)

    # 设置系统提示词
    system_prompt = request.system_prompt or _build_system_prompt()
    memory.add_system_message(system_prompt)

    # 添加用户消息到记忆
    memory.add_user_message(request.message)

    # 4. SSE 生成器
    async def generate():
        full_reply = ""
        try:
            # 发送思考状态
            yield f"data: {json.dumps({'type': 'thinking', 'content': 'AI 正在思考...'}, ensure_ascii=False)}\n\n"

            # 流式生成
            async for token in llm_service.chat_stream(messages=memory.get_messages()):
                full_reply += token
                yield f"data: {json.dumps({'type': 'token', 'content': token}, ensure_ascii=False)}\n\n"

            # 将 AI 回复添加到记忆
            memory.add_assistant_message(full_reply)

            # 保存 AI 回复到数据库
            assistant_msg = Message(
                conversation_id=conversation.id,
                role="assistant",
                content=full_reply,
                tokens=memory.total_tokens(),
            )
            db.add(assistant_msg)

            # 更新对话的 updated_at
            conversation.updated_at = datetime.utcnow()
            db.commit()

            # 发送完成信号
            yield f"data: {json.dumps({'type': 'done', 'message_id': assistant_msg.id, 'tokens': memory.total_tokens()}, ensure_ascii=False)}\n\n"

        except Exception as e:
            logger.error(f"SSE 生成出错: {e}")
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用 Nginx 缓冲
        },
    )


@router.get("/conversations")
async def list_conversations(
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    """获取对话列表（按更新时间倒序）"""
    conversations = (
        db.query(Conversation)
        .order_by(Conversation.updated_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return {
        "conversations": [c.to_dict() for c in conversations],
        "total": db.query(Conversation).count(),
    }


@router.post("/conversations")
async def create_conversation(
    data: ConversationCreate,
    db: Session = Depends(get_db),
):
    """创建新对话"""
    conversation = Conversation(title=data.title)
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation.to_dict()


@router.get("/conversations/{conversation_id}/messages")
async def get_messages(
    conversation_id: int,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """获取对话的消息历史"""
    messages = (
        db.query(Message)
        .filter_by(conversation_id=conversation_id)
        .order_by(Message.created_at.asc())
        .limit(limit)
        .all()
    )
    return {"messages": [m.to_dict() for m in messages]}
