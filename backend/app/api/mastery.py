"""
掌握度评估 API — S1 知识进阶
==============================
SSE 流式评估对话: Agent 提问 → 用户回答 → Agent 追问/评分 → ...

端点:
  POST /api/mastery/assess       — 评估对话（SSE 流式）
  GET  /api/mastery/concepts     — 掌握度列表
  GET  /api/mastery/concepts/{name} — 单个概念详情
  GET  /api/mastery/sessions     — 评估历史
"""

import json
import logging
import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.llm import llm_service
from app.services.mastery_service import mastery_service
from app.agents.mastery_agent import MASTERY_AGENT_SYSTEM_PROMPT, _build_tools

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/mastery", tags=["mastery"])


# ============================================================
# Schema
# ============================================================

class AssessRequest(BaseModel):
    concept: str = Field(..., min_length=1, max_length=200, description="要评估的概念名（标签名或自由输入）")
    notebook_id: int = Field(..., description="所属笔记库 ID")
    session_id: int | None = Field(default=None, description="已有对话 session ID")
    message: str | None = Field(default=None, max_length=5000, description="用户回复")


# ============================================================
# SSE 辅助
# ============================================================

def _sse(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


# ============================================================
# 多轮工具调用循环（替代 BaseAgent.run 以支持对话历史）
# ============================================================

async def _run_agent_turn(
    messages: list[dict],
    tool_schemas: list[dict],
    tool_registry: dict[str, callable],
    max_tool_rounds: int = 3,
) -> str:
    """
    运行一轮 Agent 对话（含工具调用）。

    1. 调用 LLM with tools → 可能返回 tool_calls 或 content
    2. 如果有 tool_calls → 执行 → 追加到 messages → 回到 1
    3. 如果返回 content → 返回最终内容

    Args:
        messages: 完整对话历史（含 system/user/assistant/tool）
        tool_schemas: OpenAI Function Calling 格式的工具列表
        tool_registry: {tool_name: async_callable} 工具执行映射
        max_tool_rounds: 最大工具调用轮数

    Returns:
        str: Agent 最终文本回复
    """
    for _ in range(max_tool_rounds):
        msg = await llm_service.chat_with_tools(
            messages, tools=tool_schemas, temperature=0.0
        )

        # ---- LLM 决定调用工具 ----
        if msg.tool_calls:
            messages.append({
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments or "{}",
                        },
                    }
                    for tc in msg.tool_calls
                ],
            })

            for tc in msg.tool_calls:
                tool_name = tc.function.name
                try:
                    tool_args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    tool_args = {}

                logger.info(f"MasteryAgent 调用工具: {tool_name} args={tool_args}")

                if tool_name in tool_registry:
                    try:
                        result = await tool_registry[tool_name](**tool_args)
                        observation = json.dumps(result, ensure_ascii=False, default=str)
                    except Exception as e:
                        observation = json.dumps({"error": str(e)}, ensure_ascii=False)
                else:
                    observation = json.dumps({"error": f"未知工具: {tool_name}"}, ensure_ascii=False)

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": observation,
                })
            continue

        # ---- LLM 给出最终文本 ----
        return msg.content or ""

    return "评估过程遇到问题，请重试。"


# ============================================================
# 端点
# ============================================================

@router.post("/assess")
async def assess(req: AssessRequest, db: Session = Depends(get_db)):
    """
    评估对话（SSE 流式）。

    新对话: 创建 session → Agent 获取笔记 → 提问
    续对话: 加载 session → 追加回复 → Agent 追问/评分

    SSE 事件:
      status  — 状态提示
      token   — 流式回复 token
      score   — 评估完成（评分 + 强弱项 + 总结）
      error   — 错误
    """

    from app.models.mastery import MasterySession as MS

    # ---- 1. 获取或创建 session ----
    if req.session_id:
        session = db.query(MS).get(req.session_id)
        if not session:
            raise HTTPException(status_code=404, detail="评估对话不存在")
        messages = session.get_messages()
        if req.message:
            messages.append({"role": "user", "content": req.message})
    else:
        messages = [
            {"role": "system", "content": MASTERY_AGENT_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"请评估我对「{req.concept}」的掌握程度。"
                    f"先调用 get_concept_notes 查看我的相关笔记，"
                    f"再调用 get_mastery_status 查看历史评估记录，"
                    f"然后开始提问。"
                ),
            },
        ]
        session = MS(concept_name=req.concept, notebook_id=req.notebook_id)
        session.set_messages(messages)
        db.add(session)
        db.commit()
        db.refresh(session)

    session_id = session.id

    # ---- 2. 构建工具注册（传入 session_id 以便 update_mastery 直接定位） ----
    tools = _build_tools(db, req.notebook_id, req.concept, session_id)
    tool_schemas = [
        {
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters,
            },
        }
        for t in tools
    ]
    tool_registry = {t.name: t.func for t in tools}

    # ---- 3. SSE generator ----
    async def generate():
        full_reply = ""
        try:
            # 状态提示
            yield _sse({"type": "status", "content": "正在准备资料..."})

            # 运行 Agent（含工具调用）
            content = await _run_agent_turn(messages, tool_schemas, tool_registry)

            if not content:
                yield _sse({"type": "error", "content": "Agent 未返回内容"})
                return

            # 流式输出 token
            for char in content:
                full_reply += char
                yield _sse({"type": "token", "content": char})
                await asyncio.sleep(0.012)

            # 保存 assistant 消息到 session
            messages.append({"role": "assistant", "content": content})
            mastery_service.save_session_messages(db, session, messages)

            # 检测是否已完成评估（调用了 update_mastery）
            score = None
            for m in messages:
                if m["role"] == "tool":
                    try:
                        obs = json.loads(m["content"])
                        if obs.get("ok") and "score" in obs:
                            score = obs["score"]
                    except (json.JSONDecodeError, KeyError):
                        pass

            if score is not None:
                concept = mastery_service.get_concept_detail(
                    db, req.concept, req.notebook_id
                )
                yield _sse({
                    "type": "score",
                    "session_id": session_id,
                    "score": score,
                    "strengths": json.loads(concept.strengths) if concept and concept.strengths else [],
                    "weaknesses": json.loads(concept.weaknesses) if concept and concept.weaknesses else [],
                    "summary": session.summary if session.summary else "",
                })

            yield _sse({"type": "done", "session_id": session_id})

        except Exception as e:
            logger.error(f"SSE 评估异常: {e}", exc_info=True)
            yield _sse({"type": "error", "content": str(e)})

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/concepts")
async def list_concepts(
    notebook_id: int = Query(..., description="笔记库 ID"),
    db: Session = Depends(get_db),
):
    """获取所有概念的掌握度列表"""
    concepts = mastery_service.get_concepts(db, notebook_id)
    return {"concepts": [c.to_dict() for c in concepts], "total": len(concepts)}


@router.get("/concepts/{concept_name:path}")
async def get_concept(
    concept_name: str,
    notebook_id: int = Query(..., description="笔记库 ID"),
    db: Session = Depends(get_db),
):
    """获取单个概念掌握度详情（含评估历史 + 评分趋势）"""
    concept = mastery_service.get_concept_detail(db, concept_name, notebook_id)
    if not concept:
        raise HTTPException(status_code=404, detail="概念不存在")

    sessions = mastery_service.get_sessions(
        db, notebook_id=notebook_id, concept_name=concept_name, limit=10
    )
    score_history = [
        {"date": s.created_at.isoformat() if s.created_at else None, "score": s.final_score}
        for s in reversed(sessions) if s.final_score is not None
    ]

    result = concept.to_dict()
    result["sessions"] = [s.to_dict() for s in sessions]
    result["score_history"] = score_history
    return {"concept": result}


@router.get("/sessions")
async def list_sessions(
    notebook_id: int = Query(..., description="笔记库 ID"),
    concept: str | None = Query(default=None, description="按概念筛选"),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """获取评估历史"""
    sessions = mastery_service.get_sessions(
        db, notebook_id=notebook_id, concept_name=concept, limit=limit
    )
    return {"sessions": [s.to_dict() for s in sessions], "total": len(sessions)}
