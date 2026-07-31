"""
笔记库数据模型
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import relationship
from app.database import Base


class Notebook(Base):
    """笔记库 — 一个独立的知识空间，包含笔记和文件夹"""
    __tablename__ = "notebooks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False)
    description = Column(String(1000), default="")

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # 关联 — 一个笔记库包含多篇笔记
    notes = relationship("Note", back_populates="notebook", lazy="dynamic")

    def to_dict(self, include_stats: bool = False) -> dict:
        result = {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_stats:
            result["note_count"] = self.notes.count()
        return result

    def __repr__(self) -> str:
        return f"<Notebook(id={self.id}, name='{self.name}')>"
