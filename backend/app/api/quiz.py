"""
出题自测 API（P6）
-----------------
POST /api/quiz/generate — 基于知识库/文件夹生成自测题
POST /api/quiz/grade    — 批改答案 + 解析 + 复习建议

出题范围: notebook_id 必填；folder 可选。
  folder 为 None/空 → 整个知识库
  folder 为路径     → 该文件夹及其所有子文件夹下的全部笔记（递归）
"""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.quiz import Quiz
from app.services.quiz_service import quiz_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/quiz", tags=["quiz"])


# ============================================================
# Schema
# ============================================================

class QuizGenerateRequest(BaseModel):
    notebook_id: int = Field(..., ge=1, description="知识库 ID")
    folder: str | None = Field(
        default=None,
        description="文件夹路径（含子文件夹，递归），None=整个知识库",
    )
    count: int = Field(default=7, ge=2, le=20, description="题目总数（默认 7 = 5选择+2简答）")


class QuizAnswerItem(BaseModel):
    question_id: str = Field(..., description="题目 ID，如 q1")
    answer: str = Field(default="", description="用户作答：选择填选项字母，简答填正文")


class QuizGradeRequest(BaseModel):
    quiz_id: int = Field(..., ge=1, description="生成的测验 ID")
    answers: list[QuizAnswerItem] = Field(default_factory=list)


# ============================================================
# 生成题目
# ============================================================

@router.post("/generate")
async def generate_quiz(data: QuizGenerateRequest, db: Session = Depends(get_db)):
    """
    根据出题范围生成自测题

    Args:
        notebook_id: 知识库 ID
        folder: 文件夹路径（递归包含子文件夹笔记）；None/空 = 整个知识库
        count: 题目总数（默认 7）

    Returns:
        {
          "quiz_id": 1,
          "notebook_id": 1,
          "folder": "AI/Agent" | null,
          "note_count": 8,
          "questions": [
            {"id": "q1", "type": "choice", "question": "...", "options": ["A. ...", "B. ...", "C. ...", "D. ..."]},
            {"id": "q2", "type": "short", "question": "..."}
          ]
        }
        注意: 返回不含正确答案（批改时由 /grade 揭示）。
    """
    try:
        quiz = await quiz_service.generate_quiz(
            db,
            notebook_id=data.notebook_id,
            folder=data.folder,
            count=data.count,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"出题异常: {e}")
        raise HTTPException(status_code=500, detail="出题服务异常，请稍后重试")

    questions = json.loads(quiz.questions_json)
    # 剥离答案与解析，答题阶段不泄露
    public = [
        {
            "id": q["id"],
            "type": q["type"],
            "question": q["question"],
            "options": q.get("options"),
        }
        for q in questions
    ]
    return {
        "quiz_id": quiz.id,
        "notebook_id": quiz.notebook_id,
        "folder": quiz.folder,
        "note_count": quiz.note_count,
        "questions": public,
    }


# ============================================================
# 批改
# ============================================================

@router.post("/grade")
async def grade_quiz(data: QuizGradeRequest, db: Session = Depends(get_db)):
    """
    批改答案

    Args:
        quiz_id: generate 返回的 quiz_id
        answers: [{"question_id": "q1", "answer": "A"}, ...]

    Returns:
        {
          "quiz_id": 1,
          "total": 7, "correct": 5, "score": 71.4,
          "results": [
            {"question_id": "q1", "correct": true, "user_answer": "A",
             "answer": "A", "explanation": "...", "comment": null},
            {"question_id": "q2", "correct": false, "user_answer": "...",
             "answer": "参考答案...", "explanation": "...", "comment": "..."}
          ],
          "summary": "总体评价 + 复习建议"
        }
    """
    try:
        grade = await quiz_service.grade_quiz(
            db,
            quiz_id=data.quiz_id,
            user_answers=[
                {"question_id": a.question_id, "answer": a.answer}
                for a in data.answers
            ],
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"批改异常: {e}")
        raise HTTPException(status_code=500, detail="批改服务异常，请稍后重试")

    quiz = db.query(Quiz).filter_by(id=data.quiz_id).first()
    return {
        "quiz_id": data.quiz_id,
        "notebook_id": quiz.notebook_id if quiz else None,
        **grade,
    }
