"""
笔记数据模型
"""

import hashlib
import logging
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, Table, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base

logger = logging.getLogger(__name__)

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

    # === 文档导入 + 同步追踪 ===
    folder = Column(String(500), default="", nullable=False)
    #   文件夹路径，如 "AI/Agent", "" 表示根目录
    source_type = Column(String(20), default="manual", nullable=False)
    #   "manual" | "md" | "docx" | "pdf" — 笔记来源
    source_path = Column(String(1000), nullable=True)
    #   原始文件路径（文件引用模式）；导入/手动创建时为 None
    content_hash = Column(String(64), nullable=True)
    #   内容 MD5 哈希（32 hex chars），用于增量同步变更检测
    last_synced_at = Column(DateTime, nullable=True)
    #   最后一次同步到 ChromaDB 向量库的时间

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
            "folder": self.folder,
            "source_type": self.source_type,
            "source_path": self.source_path,
            "last_synced_at": self.last_synced_at.isoformat() if self.last_synced_at else None,
            "tags": [t.to_dict() for t in self.tags] if self.tags else [],
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_content:
            result["content"] = self.content
        return result

    @staticmethod
    def compute_content_hash(content: str) -> str:
        """计算内容的 MD5 哈希，用于变更检测"""
        return hashlib.md5(content.encode("utf-8")).hexdigest()

    def __repr__(self) -> str:
        return f"<Note(id={self.id}, title='{self.title[:30]}')>"
