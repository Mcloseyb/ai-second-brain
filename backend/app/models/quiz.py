"""
出题自测数据模型（P6）
----------------------
Quiz 记录一次生成的测验（含全部题目与正确答案）。
批改结果填回 grade_json；题目与成绩均持久化，供历史复盘。

questions_json 结构:
    [
      {
        "id": "q1",
        "type": "choice",
        "question": "...",
        "options": ["A. ...", "B. ...", "C. ...", "D. ..."],
        "answer": "A",
        "explanation": "..."
      },
      {
        "id": "q2",
        "type": "short",
        "question": "...",
        "answer": "参考答案...",
        "explanation": "...",
        "key_points": ["关键词1", "关键词2"]
      }
    ]

grade_json 结构:
    {
      "total": 7, "correct": 5, "score": 71.4,
      "summary": "总体评价 + 复习建议",
      "results": [
        {"question_id": "q1", "correct": true, "user_answer": "A",
         "answer": "A", "explanation": "...", "comment": null},
        {"question_id": "q2", "correct": false, "user_answer": "...",
         "answer": "参考答案...", "explanation": "...", "comment": "..."}
      ]
    }
"""

import logging
from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, Text
from app.database import Base

logger = logging.getLogger(__name__)


class Quiz(Base):
    """一次 AI 出题自测记录"""

    __tablename__ = "quizzes"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # 出题范围
    notebook_id = Column(Integer, nullable=False)
    folder = Column(String(500), nullable=True)
    #   文件夹路径，如 "AI/Agent"；None 表示整个知识库
    note_count = Column(Integer, default=0)
    #   本次出题覆盖的笔记数

    # 题目与成绩
    questions_json = Column(Text, default="[]", nullable=False)
    grade_json = Column(Text, nullable=True)
    #   未批改时为 None

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<Quiz(id={self.id}, notebook_id={self.notebook_id}, folder='{self.folder}')>"
