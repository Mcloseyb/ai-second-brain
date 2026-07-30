"""
消息模型 — 对话中的每一条消息
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, JSON
from app.database import Base


class Message(Base):
    """消息 — 一条对话记录"""

    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(
        Integer, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    role = Column(
        String(20), nullable=False
    )  # 'user' | 'assistant' | 'system'
    content = Column(Text, nullable=False)
    tokens = Column(Integer, default=0)  # 这条消息的 token 数（估算）
    sources = Column(JSON, nullable=True)  # RAG 引用来源 [{doc_id, chunk_id, text}]
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "conversation_id": self.conversation_id,
            "role": self.role,
            "content": self.content,
            "tokens": self.tokens,
            "sources": self.sources,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        preview = self.content[:50] if self.content else ""
        return f"<Message(id={self.id}, role='{self.role}', content='{preview}...')>"
