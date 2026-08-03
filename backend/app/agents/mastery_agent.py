"""
MasteryAgent — 刻意练习教练（S1 知识进阶）
===========================================
Agent 通过苏格拉底式对话评估用户对概念的掌握程度。

工具:
  - get_concept_notes:    查找相关笔记（标签匹配 + 语义搜索）
  - get_mastery_status:   查询历史评估记录
  - update_mastery:       对话结束后保存评估结果

使用方式（API 层每次调用重建 Agent，绑定当前 db session）:
    from app.agents.mastery_agent import build_mastery_agent
    agent = build_mastery_agent(db, notebook_id)
    output = await agent.run(user_input)
"""

import json
import logging

from sqlalchemy.orm import Session

from app.agents.base import ToolDefinition, build_agent
from app.services.mastery_service import mastery_service

logger = logging.getLogger(__name__)

# ============================================================
# System Prompt
# ============================================================

MASTERY_AGENT_SYSTEM_PROMPT = """你是刻意练习教练。你的任务是通过苏格拉底式对话，评估用户对某个概念的真正理解程度——不是记忆能力，而是理解深度。

## 你的工作方式

1. **先了解范围**: 调用 get_concept_notes 查看用户有哪些相关笔记，调用 get_mastery_status 查看历史评估记录
2. **开放式提问**: 用"用你自己的话说说……"开头，避免选择题式的提问
3. **追问检验**: 如果用户回答得好 → 追问更深或更偏应用的问题；如果用户只是复述笔记 → 换一个笔记没覆盖的角度
4. **苏格拉底式引导**: 不要直接告诉答案。如果用户卡住了，用一个更简单的类比或例子引导
5. **控制节奏**: 一问一答，不要一口气问多个问题。每个回复以一个问题结束

## 评分标准（0-100）

| 分数 | 含义 |
|------|------|
| 90-100 | 能用自己的话清晰解释，能举一反三，能关联其他概念 |
| 70-89  | 理解核心思想，但换个角度就犹豫，或部分细节模糊 |
| 50-69  | 能复述笔记内容，但深度不够，追问就会露馅 |
| 30-49  | 基本概念有混淆，需要回头重新学习 |
| 0-29   | 完全没理解 |

## 何时结束评估

- 2-3 轮问答后你已经能清晰判断用户的掌握程度 → 调用 update_mastery 给出评分
- 用户明确表示不想继续 → 直接给出当前评估
- 已经问了 5 轮还没把握 → 给出暂时评分并说明不确定性

## 反馈要求

调用 update_mastery 时:
- `score`: 综合评分 0-100
- `strengths`: 用户理解得好的点（2-3 条，用自己的话）
- `weaknesses`: 需要加强的点（1-3 条，具体可操作）
- `summary`: 一段鼓励性的总结，包含评分依据 + 学习建议（2-4 句话）

## 语气

- 友好、鼓励，像教练而不是考官
- 用"你"而不是"该同学"
- 表扬具体（"你对 QKV 的解释很清楚"），批评温和（"Multi-Head 这块可以再想想"）
- 每次回复不要太长，2-4 句 + 一个问题"""


# ============================================================
# 工具定义（闭包绑定 db session）
# ============================================================

def _build_tools(
    db: Session, notebook_id: int, concept_name: str, session_id: int | None = None
) -> list[ToolDefinition]:
    """构建 Agent 工具（每个请求独立，闭包捕获 db + notebook_id + session_id）"""

    async def get_concept_notes(_concept_name: str) -> dict:
        """查找与该概念相关的笔记内容，供评估参考"""
        notes = await mastery_service.find_related_notes(
            db, concept_name=_concept_name, notebook_id=notebook_id
        )
        if not notes:
            return {"count": 0, "notes": [], "message": "未找到相关笔记，请基于常识提问"}
        return {
            "count": len(notes),
            "notes": [
                {"title": n["title"], "content": n["content"], "folder": n["folder"]}
                for n in notes
            ],
        }

    async def get_mastery_status(_concept_name: str) -> dict:
        """查询该概念的历史评估记录"""
        concept = mastery_service.get_concept_detail(
            db, concept_name=_concept_name, notebook_id=notebook_id
        )
        if not concept:
            return {
                "exists": False,
                "message": "首次评估，无历史记录",
            }
        return {
            "exists": True,
            "mastery_score": concept.mastery_score,
            "assessment_count": concept.assessment_count,
            "last_assessed_at": concept.last_assessed_at.isoformat() if concept.last_assessed_at else None,
            "strengths": json.loads(concept.strengths) if concept.strengths else [],
            "weaknesses": json.loads(concept.weaknesses) if concept.weaknesses else [],
        }

    async def update_mastery(
        score: float,
        strengths: list[str],
        weaknesses: list[str],
        summary: str,
    ) -> dict:
        """保存评估结果到数据库。评估结束时必须调用。"""
        score = max(0.0, min(100.0, float(score)))
        if not isinstance(strengths, list):
            strengths = []
        if not isinstance(weaknesses, list):
            weaknesses = []
        summary = str(summary or "")[:500]

        # 通过 session_id 直接找到当前 session
        from app.models.mastery import MasterySession as MS

        if session_id:
            s = db.query(MS).get(session_id)
            if s:
                mastery_service.complete_session(
                    db, s, score, summary,
                    [str(x)[:100] for x in strengths[:5]],
                    [str(x)[:100] for x in weaknesses[:5]],
                )
                logger.info(
                    f"评估完成: concept='{concept_name}' session={session_id} "
                    f"score={score}"
                )
                return {"ok": True, "score": score, "message": "评估已保存"}

        # 降级: 查找最近 session
        sessions = mastery_service.get_sessions(
            db, notebook_id=notebook_id, concept_name=concept_name, limit=1
        )
        if sessions:
            mastery_service.complete_session(
                db, sessions[0], score, summary,
                [str(x)[:100] for x in strengths[:5]],
                [str(x)[:100] for x in weaknesses[:5]],
            )
            logger.info(
                f"评估完成（降级）: concept='{concept_name}' score={score}"
            )
            return {"ok": True, "score": score, "message": "评估已保存"}

        logger.warning(f"未找到进行中的 session，跳过 mastery 更新")
        return {"ok": False, "error": "会话不存在"}

    return [
        ToolDefinition(
            name="get_concept_notes",
            description="查找与该概念相关的用户笔记内容（标题、正文摘要、文件夹）。调用后你会看到用户写了哪些相关笔记，用于评估提问。",
            parameters={
                "type": "object",
                "properties": {
                    "_concept_name": {
                        "type": "string",
                        "description": "概念名（通常是当前评估的概念）",
                    },
                },
                "required": ["_concept_name"],
            },
            func=get_concept_notes,
        ),
        ToolDefinition(
            name="get_mastery_status",
            description="查询该概念的历史评估记录：上次评分、强弱项、评估次数。用于了解用户的学习轨迹。",
            parameters={
                "type": "object",
                "properties": {
                    "_concept_name": {
                        "type": "string",
                        "description": "概念名",
                    },
                },
                "required": ["_concept_name"],
            },
            func=get_mastery_status,
        ),
        ToolDefinition(
            name="update_mastery",
            description="保存评估结果。当你已经通过 2-3 轮对话充分了解了用户的掌握程度后，调用此工具持久化评分。必须调用！",
            parameters={
                "type": "object",
                "properties": {
                    "score": {
                        "type": "number",
                        "description": "综合评分 0-100",
                        "minimum": 0,
                        "maximum": 100,
                    },
                    "strengths": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "强项列表（2-3 条具体描述）",
                        "maxItems": 5,
                    },
                    "weaknesses": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "需加强的点（1-3 条具体可操作建议）",
                        "maxItems": 5,
                    },
                    "summary": {
                        "type": "string",
                        "description": "鼓励性总结，含评分依据 + 学习建议（2-4 句）",
                        "maxLength": 500,
                    },
                },
                "required": ["score", "strengths", "weaknesses", "summary"],
            },
            func=update_mastery,
        ),
    ]


def build_mastery_agent(db: Session, notebook_id: int, concept_name: str):
    """
    构建 MasteryAgent 实例。
    每次 API 调用创建一个新 Agent，工具闭包绑定当前 db session。
    """
    tools = _build_tools(db, notebook_id, concept_name)
    return build_agent(
        name="mastery_agent",
        description="刻意练习教练 — 通过苏格拉底式对话评估概念掌握度",
        system_prompt=MASTERY_AGENT_SYSTEM_PROMPT,
        tools=tools,
        max_steps=5,
    )
