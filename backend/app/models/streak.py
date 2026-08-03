"""
打卡追踪数据模型 — 温故知新
===========================
UserStreak: 连续复习天数统计
"""

import logging
from datetime import datetime, date
from sqlalchemy import Column, Integer, Date, DateTime, ForeignKey
from app.database import Base

logger = logging.getLogger(__name__)


class UserStreak(Base):
    """用户连续打卡记录 — 每个笔记库独立追踪"""

    __tablename__ = "user_streaks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    notebook_id = Column(Integer, ForeignKey("notebooks.id", ondelete="CASCADE"),
                         nullable=False, unique=True)

    current_streak = Column(Integer, default=0, nullable=False)
    # 当前连续天数

    longest_streak = Column(Integer, default=0, nullable=False)
    # 历史最长连续天数

    last_review_date = Column(Date, nullable=True)
    # 上次复习日期（防同一天多次打卡）

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def to_dict(self) -> dict:
        return {
            "current_streak": self.current_streak,
            "longest_streak": self.longest_streak,
            "last_review_date": self.last_review_date.isoformat() if self.last_review_date else None,
        }

    def __repr__(self) -> str:
        return (f"<UserStreak(notebook={self.notebook_id}, "
                f"streak={self.current_streak}/{self.longest_streak})>")
