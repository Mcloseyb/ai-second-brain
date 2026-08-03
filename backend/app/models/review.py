"""
复习追踪数据模型 — 温故知新
===========================
NoteReviewState: 每篇笔记的 SM-2 遗忘曲线状态
ReviewLog:       每次复习的记录
"""

import logging
from datetime import datetime
from sqlalchemy import Column, Integer, Float, String, DateTime, Text, ForeignKey
from app.database import Base

logger = logging.getLogger(__name__)


class NoteReviewState(Base):
    """每篇笔记的 SM-2 遗忘曲线状态 — 驱动复习调度"""

    __tablename__ = "note_review_states"

    id = Column(Integer, primary_key=True, autoincrement=True)
    note_id = Column(Integer, ForeignKey("notes.id", ondelete="CASCADE"),
                     nullable=False, unique=True)

    ease_factor = Column(Float, default=2.5, nullable=False)
    # SM-2 难度系数，下限 1.3

    interval_days = Column(Integer, default=0, nullable=False)
    # 当前间隔天数（0 = 新笔记，尚未复习过）

    repetitions = Column(Integer, default=0, nullable=False)
    # 连续正确次数（部分正确则重置为 0）

    next_review_at = Column(DateTime, nullable=True)
    # 下次复习时间；NULL = 从未复习，视为立即到期

    last_review_at = Column(DateTime, nullable=True)
    # 上次复习时间

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "note_id": self.note_id,
            "ease_factor": round(self.ease_factor, 2),
            "interval_days": self.interval_days,
            "repetitions": self.repetitions,
            "next_review_at": self.next_review_at.isoformat() if self.next_review_at else None,
            "last_review_at": self.last_review_at.isoformat() if self.last_review_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self) -> str:
        return (f"<NoteReviewState(note={self.note_id}, ef={self.ease_factor:.1f}, "
                f"interval={self.interval_days}d, reps={self.repetitions})>")


class ReviewLog(Base):
    """复习记录 — 每次测验里某篇笔记出的题+答对情况"""

    __tablename__ = "review_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    note_id = Column(Integer, ForeignKey("notes.id", ondelete="CASCADE"), nullable=False)
    cluster_id = Column(Integer, ForeignKey("concept_clusters.id", ondelete="SET NULL"),
                        nullable=True)
    quiz_id = Column(Integer, ForeignKey("quizzes.id", ondelete="SET NULL"), nullable=True)

    correct_count = Column(Integer, default=0, nullable=False)
    total_count = Column(Integer, default=0, nullable=False)

    rating = Column(String(10), nullable=True)
    # 用户记忆自评: "again" | "hard" | "good" | "easy"；旧数据 NULL

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "note_id": self.note_id,
            "cluster_id": self.cluster_id,
            "quiz_id": self.quiz_id,
            "correct_count": self.correct_count,
            "total_count": self.total_count,
            "correct_rate": round(self.correct_count / self.total_count, 2)
            if self.total_count > 0 else 0.0,
            "rating": self.rating,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return (f"<ReviewLog(note={self.note_id}, "
                f"correct={self.correct_count}/{self.total_count})>")
