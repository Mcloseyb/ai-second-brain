"""
笔记数据模型
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, Table, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base

# 笔记-标签 多对多关联表
note_tags = Table(
    "note_tags",
    Base.metadata,
    Column("note_id", Integer, ForeignKey("notes.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", Integer, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)


class Note(Base):
    __tablename__ = "notes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(500), default="Untitled", nullable=False)
    content = Column(Text, default="", nullable=False)
    format = Column(String(20), default="markdown")  # "markdown" | "richtext"
    word_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # 关联标签（多对多）
    tags = relationship("Tag", secondary=note_tags, back_populates="notes", lazy="selectin")

    def to_dict(self, include_content: bool = True) -> dict:
        result = {
            "id": self.id,
            "title": self.title,
            "format": self.format,
            "word_count": self.word_count,
            "tags": [t.to_dict() for t in self.tags] if self.tags else [],
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_content:
            result["content"] = self.content
        return result

    def __repr__(self) -> str:
        return f"<Note(id={self.id}, title='{self.title[:30]}')>"
