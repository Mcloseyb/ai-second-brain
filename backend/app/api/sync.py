"""
同步 API
-------
POST /api/sync/now          — 手动全量同步
POST /api/sync/auto/toggle   — 开关定时自动同步
GET  /api/sync/auto/status   — 查询定时同步状态
GET  /api/sync/status        — 同步状态概览
GET  /api/sync/pending       — 待同步笔记列表
POST /api/sync/notes/{id}    — 同步单篇笔记
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.sync_service import sync_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sync", tags=["sync"])


# ============================================================
# Schema
# ============================================================

class ToggleAutoRequest(BaseModel):
    enabled: bool = Field(..., description="是否启用定时自动同步")
    interval_minutes: int = Field(default=30, ge=5, le=1440, description="同步间隔（分钟）")


# ============================================================
# Endpoints
# ============================================================


@router.post("/auto/toggle")
async def toggle_auto_sync(req: ToggleAutoRequest, request: Request):
    """
    启用/禁用定时自动同步

    Args:
        enabled: 是否启用
        interval_minutes: 同步间隔（分钟），默认 30，范围 5-1440

    Returns:
        { "auto_sync_enabled": true, "interval_minutes": 30 }
    """
    request.app.state.auto_sync_enabled = req.enabled
    request.app.state.sync_interval = req.interval_minutes * 60
    logger.info(f"定时同步: {'启用' if req.enabled else '禁用'} (间隔 {req.interval_minutes} 分钟)")
    return {
        "auto_sync_enabled": req.enabled,
        "interval_minutes": req.interval_minutes,
    }


@router.get("/auto/status")
async def auto_sync_status(request: Request):
    """
    查询定时同步状态

    Returns:
        { "auto_sync_enabled": false, "interval_minutes": 30, "last_sync_at": null }
    """
    return {
        "auto_sync_enabled": request.app.state.auto_sync_enabled,
        "interval_minutes": request.app.state.sync_interval // 60,
        "last_sync_at": (
            datetime.fromtimestamp(request.app.state.last_sync_at, tz=timezone.utc).isoformat()
            if request.app.state.last_sync_at else None
        ),
    }


@router.post("/now")
async def sync_now(db: Session = Depends(get_db)):
    """
    手动触发全量同步（增量：仅同步有变更的笔记）

    Returns:
        { "report": { "total": 50, "synced": 3, "skipped": 47, "failed": 0 } }
    """
    report = await sync_service.sync_all(db)
    return {
        "report": {
            "total": report.total,
            "synced": report.synced,
            "skipped": report.skipped,
            "failed": report.failed,
            "results": [
                {"note_id": r.note_id, "title": r.title, "status": r.status, "detail": r.detail}
                for r in report.results
            ],
        }
    }


@router.get("/status")
async def sync_status(db: Session = Depends(get_db)):
    """
    获取同步状态概览

    Returns:
        {
            "total_notes": 50,
            "synced": 47,
            "pending": 3,
            "never_synced": 0,
        }
    """
    return sync_service.get_status(db)


@router.get("/pending")
async def sync_pending(db: Session = Depends(get_db)):
    """
    获取待同步的笔记列表（content_hash 不匹配或从未同步）

    Returns:
        { "pending": [{ "id": 1, "title": "...", "folder": "..." }, ...] }
    """
    pending = sync_service.get_pending(db)
    return {
        "pending": [
            {
                "id": n.id,
                "title": n.title,
                "folder": n.folder,
                "source_type": n.source_type,
                "last_synced_at": n.last_synced_at.isoformat() if n.last_synced_at else None,
            }
            for n in pending
        ]
    }


@router.post("/notes/{note_id}")
async def sync_single_note(note_id: int, db: Session = Depends(get_db)):
    """
    同步单篇笔记到向量库

    Args:
        note_id: 笔记 ID

    Returns:
        { "result": { "note_id": 1, "title": "...", "status": "synced", "detail": "..." } }
    """
    result = await sync_service.sync_note(db, note_id)
    if result.status == "error" and "不存在" in result.detail:
        raise HTTPException(status_code=404, detail=result.detail)

    return {
        "result": {
            "note_id": result.note_id,
            "title": result.title,
            "status": result.status,
            "detail": result.detail,
        }
    }
