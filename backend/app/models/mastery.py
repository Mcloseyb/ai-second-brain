"""
掌握度追踪数据模型 — S1 知识进阶
===================================
ConceptMastery:  概念掌握度记录（每概念、每笔记库存一条）
MasterySession:  评估对话记录（含完整消息历史）
"""

import json
import logging
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, ForeignKey
from app.database import Base

logger = logging.getLogger(__name__)


class ConceptMastery(Base):
    """概念掌握度 — 每个概念在每个笔记库下独立追踪"""

    __tablename__ = "concept_masteries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    concept_name = Column(String(200), nullable=False, index=True)
    # 概念名 — 可以是标签名、用户自定义输入、"标签/子概念"
    notebook_id = Column(Integer, ForeignKey("notebooks.id", ondelete="CASCADE"), nullable=False)

    mastery_score = Column(Float, default=0.0, nullable=False)
    # 掌握度 0-100（Agent 综合评估，非公式计算）

    assessment_count = Column(Integer, default=0, nullable=False)
    # 被评估次数

    last_assessed_at = Column(DateTime, nullable=True)
    # 最近一次评估时间

    strengths = Column(Text, default="[]", nullable=False)
    # JSON 数组: ["能用自己话解释QKV", ...]

    weaknesses = Column(Text, default="[]", nullable=False)
    # JSON 数组: ["Multi-Head 直觉理解不够", ...]

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def to_dict(self, include_sessions: bool = False) -> dict:
        result = {
            "id": self.id,
            "concept_name": self.concept_name,
            "notebook_id": self.notebook_id,
            "mastery_score": self.mastery_score,
            "assessment_count": self.assessment_count,
            "last_assessed_at": self.last_assessed_at.isoformat() if self.last_assessed_at else None,
            "strengths": _parse_json(self.strengths, []),
            "weaknesses": _parse_json(self.weaknesses, []),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_sessions and hasattr(self, 'sessions'):
            result["sessions"] = [s.to_dict() for s in self.sessions]
        return result

    def __repr__(self) -> str:
        return f"<ConceptMastery(concept='{self.concept_name}', score={self.mastery_score})>"


class MasterySession(Base):
    """评估对话记录 — 每次 Agent 评估的完整对话"""

    __tablename__ = "mastery_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    concept_name = Column(String(200), nullable=False)
    notebook_id = Column(Integer, ForeignKey("notebooks.id", ondelete="CASCADE"), nullable=False)

    messages = Column(Text, default="[]", nullable=False)
    # JSON 数组: [{"role":"system"|"user"|"assistant"|"tool", "content":"..."}, ...]
    # 含完整的 System Prompt + 对话 + 工具调用记录

    final_score = Column(Float, nullable=True)
    # 最终评分 0-100；None = 评估进行中

    summary = Column(Text, nullable=True)
    # Agent 评估总结（评分依据 + 建议）

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "concept_name": self.concept_name,
            "notebook_id": self.notebook_id,
            "message_count": len(_parse_json(self.messages, [])),
            "final_score": self.final_score,
            "summary": self.summary,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def get_messages(self) -> list[dict]:
        """解析消息 JSON"""
        return _parse_json(self.messages, [])

    def set_messages(self, msgs: list[dict]) -> None:
        """序列化消息到 JSON"""
        self.messages = json.dumps(msgs, ensure_ascii=False)

    def __repr__(self) -> str:
        return f"<MasterySession(id={self.id}, concept='{self.concept_name}', score={self.final_score})>"


def _parse_json(raw: str | None, default):
    """安全解析 JSON，失败返回 default"""
    if not raw:
        return default
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return default
