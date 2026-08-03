"""
错题记录 — 温故知新
====================
WrongQuestion: 每次批改中答错的题目完整保存，支持原题重温
"""

import logging
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, ForeignKey
from app.database import Base

logger = logging.getLogger(__name__)


class WrongQuestion(Base):
    """答错的题目 — 保存完整题目 JSON、用户答案、正确答案，供错题重温"""

    __tablename__ = "wrong_questions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    notebook_id = Column(Integer, ForeignKey("notebooks.id", ondelete="CASCADE"),
                         nullable=False)
    note_id = Column(Integer, ForeignKey("notes.id", ondelete="CASCADE"),
                     nullable=False)
    cluster_id = Column(Integer, ForeignKey("concept_clusters.id", ondelete="SET NULL"),
                        nullable=True)
    quiz_id = Column(Integer, ForeignKey("quizzes.id", ondelete="SET NULL"), nullable=True)

    question_json = Column(Text, nullable=False)
    # 完整题目 JSON: { question, options[], answer, explanation, note_title }

    user_answer = Column(String(5), nullable=False)
    # 用户选的答案 A/B/C/D

    reviewed = Column(Boolean, default=False, nullable=False)
    # 是否已重温过

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self) -> dict:
        import json
        q = json.loads(self.question_json) if self.question_json else {}
        return {
            "id": self.id,
            "notebook_id": self.notebook_id,
            "note_id": self.note_id,
            "cluster_id": self.cluster_id,
            "quiz_id": self.quiz_id,
            "question": q.get("question", ""),
            "options": q.get("options", []),
            "answer": q.get("answer", ""),
            "explanation": q.get("explanation", ""),
            "note_title": q.get("note_title", ""),
            "user_answer": self.user_answer,
            "reviewed": self.reviewed,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f"<WrongQuestion(id={self.id}, note={self.note_id}, reviewed={self.reviewed})>"
