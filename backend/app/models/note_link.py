"""
笔记链接数据模型 — 记录笔记间的引用关系（P5 双向链接）
"""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, DateTime, ForeignKey, UniqueConstraint, Index,
)
from app.database import Base


class NoteLink(Base):
    __tablename__ = "note_links"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_note_id = Column(Integer, ForeignKey("notes.id", ondelete="CASCADE"), nullable=False)
    target_note_id = Column(Integer, ForeignKey("notes.id", ondelete="CASCADE"), nullable=False)
    link_type = Column(String(20), default="semantic", nullable=False)
    #   "semantic" | "title" | "manual"
    #     semantic = AI 语义相似（实时计算，不落库）
    #     title    = 正文包含目标笔记标题（自动检测）
    #     manual   = 用户手动确认的链接
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # 同一对 (source, target, type) 只允许一条
    __table_args__ = (
        UniqueConstraint("source_note_id", "target_note_id", "link_type", name="uq_note_link"),
        Index("ix_note_links_target", "target_note_id"),
    )

    def __repr__(self) -> str:
        return f"<NoteLink {self.source_note_id} → {self.target_note_id} ({self.link_type})>"
