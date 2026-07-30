"""
标签数据模型
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import relationship
from app.database import Base
from app.models.note import note_tags


class Tag(Base):
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False)
    color = Column(String(20), default="#6B9FFF")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # 反向关联
    notes = relationship("Note", secondary=note_tags, back_populates="tags", lazy="selectin")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "color": self.color,
            "note_count": len(self.notes) if self.notes else 0,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f"<Tag(id={self.id}, name='{self.name}')>"
