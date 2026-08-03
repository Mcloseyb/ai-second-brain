"""
温故知新 API — 聚类 / 复习调度 / 出题 / 批改 / 打卡 / 日历
===========================================================
"""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.cluster_service import cluster_service
from app.services.review_service import review_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/review", tags=["review"])

# ── 请求 Schema ────────────────────────────────────


class GenerateRequest(BaseModel):
    cluster_id: int
    scope: str = Field(default="due", description="due|all|errors|new")
    count: int = Field(default=10, ge=5, le=30)


class GradeRequest(BaseModel):
    quiz_id: int
    answers: list[dict]  # [{"question_id": "q1", "answer": "A"}, ...]
    ratings: list[dict] | None = None  # [{"note_id": 1, "rating": "good"}, ...]


class FreeGenerateRequest(BaseModel):
    notebook_id: int
    cluster_id: int | None = None
    folder: str | None = None
    count: int = Field(default=10, ge=5, le=30)


# ── 聚类 ───────────────────────────────────────────


@router.post("/clusters/recluster")
async def recluster(
    notebook_id: int = Query(..., description="笔记库 ID"),
    db: Session = Depends(get_db),
):
    """全量重聚类 + Agent 命名"""
    try:
        result = await cluster_service.recluster_all(db, notebook_id)
        return result
    except Exception as e:
        logger.error(f"重聚类失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/clusters")
async def list_clusters(
    notebook_id: int = Query(..., description="笔记库 ID"),
    db: Session = Depends(get_db),
):
    """簇列表 + 掌握度统计"""
    clusters = cluster_service.get_clusters(db, notebook_id)
    # 为每个簇附加掌握度统计
    result = []
    for c in clusters:
        mastery = review_service.cluster_mastery(db, c["id"])
        c["mastery"] = mastery
        result.append(c)
    return {"clusters": result}


@router.get("/clusters/{cluster_id}")
async def cluster_detail(
    cluster_id: int,
    db: Session = Depends(get_db),
):
    """单个簇详情（含笔记列表 + SM-2 状态 + 掌握度）"""
    detail = cluster_service.get_cluster_detail(db, cluster_id)
    if not detail:
        raise HTTPException(status_code=404, detail="簇不存在")

    # 为每篇笔记附加 SM-2 状态 + 掌握度
    from app.models.review import NoteReviewState
    from app.services.review_service import mastery_level

    note_ids = [n["id"] for n in (detail.get("notes") or [])]
    if note_ids:
        states = db.query(NoteReviewState).filter(
            NoteReviewState.note_id.in_(note_ids)
        ).all()
        state_map = {s.note_id: s for s in states}

        enriched_notes = []
        for n in (detail.get("notes") or []):
            s = state_map.get(n["id"])
            n["sm2"] = s.to_dict() if s else None
            n["mastery"] = mastery_level(s) if s else "new"
            enriched_notes.append(n)
        detail["notes"] = enriched_notes

    # 附加簇级掌握度统计
    detail["mastery"] = review_service.cluster_mastery(db, cluster_id)

    return detail


# ── 复习：出题 ──────────────────────────────────────


@router.post("/generate")
async def generate_quiz(
    req: GenerateRequest,
    db: Session = Depends(get_db),
):
    """从指定簇生成复习测验（支持四种 scope）"""
    if req.scope not in ("due", "all", "errors", "new"):
        raise HTTPException(status_code=400, detail="scope 必须是 due/all/errors/new")
    try:
        quiz = await review_service.generate_review_quiz(
            db, req.cluster_id, req.scope, req.count
        )
        questions = json.loads(quiz.questions_json or "[]")
        safe_questions = [
            {k: v for k, v in q.items() if k != "answer"}
            for q in questions
        ]
        return {
            "quiz_id": quiz.id,
            "note_count": quiz.note_count,
            "questions": safe_questions,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"生成测验失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ── 复习：批改 ──────────────────────────────────────


@router.post("/grade")
async def grade_quiz(
    req: GradeRequest,
    db: Session = Depends(get_db),
):
    """批改复习测验 + 更新 SM-2（支持四档评分） + 更新打卡"""
    try:
        result = await review_service.grade_review_quiz(
            db, req.quiz_id, req.answers, req.ratings
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"批改失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ── 打卡 ───────────────────────────────────────────


@router.get("/streak")
async def get_streak(
    notebook_id: int = Query(..., description="笔记库 ID"),
    db: Session = Depends(get_db),
):
    """获取连续打卡状态"""
    return review_service.get_streak(db, notebook_id)


# ── 日历 ───────────────────────────────────────────


@router.get("/calendar")
async def review_calendar(
    notebook_id: int = Query(..., description="笔记库 ID"),
    year: int = Query(..., description="年份"),
    month: int = Query(..., ge=1, le=12, description="月份"),
    db: Session = Depends(get_db),
):
    """月度复习热力图"""
    return review_service.get_calendar(db, notebook_id, year, month)


@router.get("/calendar/day")
async def calendar_day_detail(
    notebook_id: int = Query(..., description="笔记库 ID"),
    date: str = Query(..., description="日期 YYYY-MM-DD"),
    db: Session = Depends(get_db),
):
    """某一天的复习详情"""
    try:
        return review_service.get_day_detail(db, notebook_id, date)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"获取日历详情失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ── 自由出题（不计入 SM-2） ────────────────────────


@router.post("/free-generate")
async def free_generate_quiz(
    req: FreeGenerateRequest,
    db: Session = Depends(get_db),
):
    """自由出题（手动选簇/文件夹 + 题量）"""
    try:
        quiz = await review_service.generate_free_quiz(
            db, req.notebook_id, req.cluster_id, req.folder, req.count
        )
        questions = json.loads(quiz.questions_json or "[]")
        safe_questions = [
            {k: v for k, v in q.items() if k != "answer"}
            for q in questions
        ]
        return {
            "quiz_id": quiz.id,
            "note_count": quiz.note_count,
            "questions": safe_questions,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"自由出题失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/free-grade")
async def free_grade_quiz(
    req: GradeRequest,
    db: Session = Depends(get_db),
):
    """自由出题批改（不更新 SM-2，不打卡）"""
    try:
        result = await review_service.grade_free_quiz(
            db, req.quiz_id, req.answers
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"批改失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
