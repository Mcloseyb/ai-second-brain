"""
知识点收藏数据模型 — 温故知新
=============================
KnowledgeBookmark: 用户收藏的知识点（关联到来源笔记）
"""

import logging
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey
from app.database import Base

logger = logging.getLogger(__name__)


class KnowledgeBookmark(Base):
    """用户收藏的知识点 — 来自测验中的错题或重点"""

    __tablename__ = "knowledge_bookmarks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    notebook_id = Column(Integer, ForeignKey("notebooks.id", ondelete="CASCADE"),
                         nullable=False)
    note_id = Column(Integer, ForeignKey("notes.id", ondelete="CASCADE"),
                     nullable=False)
    cluster_id = Column(Integer, ForeignKey("concept_clusters.id", ondelete="SET NULL"),
                        nullable=True)

    question = Column(Text, nullable=False)
    # 收藏的知识点内容（题目文本）

    explanation = Column(Text, default="", nullable=False)
    # AI 解答

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "notebook_id": self.notebook_id,
            "note_id": self.note_id,
            "cluster_id": self.cluster_id,
            "question": self.question,
            "explanation": self.explanation,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f"<KnowledgeBookmark(id={self.id}, note={self.note_id})>"
