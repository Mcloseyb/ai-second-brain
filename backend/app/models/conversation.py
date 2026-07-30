"""
对话会话模型
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime
from app.database import Base


class Conversation(Base):
    """对话会话 — 一次对话一个 Conversation"""

    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(200), default="新对话", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self) -> str:
        return f"<Conversation(id={self.id}, title='{self.title}')>"
