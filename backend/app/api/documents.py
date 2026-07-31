"""
文档导入 API
-----------
POST /api/documents/import          — 上传文件导入
POST /api/documents/import-from-path — 本地路径导入
"""

import logging
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.note import Note
from app.services.note_service import note_service
from app.core.document_parser import (
    document_parser,
    DocumentParseError,
    SUPPORTED_EXTENSIONS,
)
from app.core.rag_engine import rag_engine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/documents", tags=["documents"])


# ============================================================
# Schema
# ============================================================

class ImportFromPathRequest(BaseModel):
    file_path: str = Field(..., description="本地文件路径")
    folder: str = Field(default="", max_length=500, description="目标文件夹")
    tags: list[str] = Field(default_factory=list, description="初始标签")


# ============================================================
# Endpoints
# ============================================================

@router.post("/import", status_code=201)
async def import_file(
    file: UploadFile = File(...),
    folder: str = Form(default=""),
    tags: str = Form(default=""),
    db: Session = Depends(get_db),
):
    """
    上传文件导入为笔记

    流程: 保存文件 → 解析为 Markdown → 创建 Note → 自动向量化

    Args:
        file: 上传的文件（.md/.docx/.pdf/.txt）
        folder: 目标文件夹路径，如 "AI/Agent"；空字符串 = 根目录
        tags: 逗号分隔的标签，如 "AI,Agent,ReAct"

    Returns:
        { "note": {...}, "synced": true }
    """
    # ---- 1. 校验 ----
    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名为空")

    ext = Path(file.filename).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的格式 '{ext}'，支持: {', '.join(sorted(SUPPORTED_EXTENSIONS))}",
        )

    # 检查文件大小（fastapi 默认无限制，手动校验）
    content = await file.read()
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"文件超过 {settings.max_upload_size_mb}MB 限制",
        )

    if len(content) == 0:
        raise HTTPException(status_code=400, detail="文件内容为空")

    # ---- 2. 保存文件到上传目录 ----
    settings.upload_path.mkdir(parents=True, exist_ok=True)
    safe_name = f"{uuid.uuid4().hex[:8]}_{file.filename}"
    saved_path = settings.upload_path / safe_name
    saved_path.write_bytes(content)
    logger.info(f"文件已保存: {saved_path}")

    # ---- 3. 解析文档 ----
    try:
        parsed = await document_parser.parse_file(str(saved_path))
    except DocumentParseError as e:
        logger.error(f"解析失败: {e}")
        # 清理已保存的文件
        try:
            saved_path.unlink()
        except OSError:
            pass
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"解析异常: {e}")
        try:
            saved_path.unlink()
        except OSError:
            pass
        raise HTTPException(status_code=500, detail=f"文档解析失败: {e}")

    if not parsed.content.strip():
        try:
            saved_path.unlink()
        except OSError:
            pass
        raise HTTPException(status_code=400, detail="解析后内容为空")

    # ---- 4. 创建笔记 ----
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    note = await note_service.create(
        db,
        title=parsed.title,
        content=parsed.content,
        tags=tag_list,
    )

    # 补充导入元数据
    note.folder = folder.strip()
    note.source_type = parsed.source_type
    note.source_path = str(saved_path.relative_to(settings.upload_path.parent))
    note.content_hash = Note.compute_content_hash(parsed.content)
    note.word_count = parsed.word_count
    db.commit()
    db.refresh(note)

    # ---- 5. 自动向量化（note_service.create 已做，这里确认同步状态） ----
    synced = note.last_synced_at is not None
    if not synced:
        # note_service.create 中的向量化如果失败了，这里重试一次
        try:
            await rag_engine.index_note(note.id, note.title, note.content)
            from datetime import datetime, timezone
            note.last_synced_at = datetime.now(timezone.utc)
            note.content_hash = Note.compute_content_hash(parsed.content)
            db.commit()
            synced = True
            logger.info(f"导入笔记 {note.id} 重试向量化成功")
        except Exception as e:
            logger.error(f"导入时向量化失败 — 笔记 {note.id}: {e}")
        # 向量化失败不阻止导入，后续可手动同步

    # ---- 6. 清理（可选：保留文件用于后续重新同步） ----
    # 导入模式保留文件在 uploads 下，方便追溯

    return {
        "note": note.to_dict(include_content=True),
        "synced": synced,
    }


@router.post("/import-from-path", status_code=201)
async def import_from_path(
    req: ImportFromPathRequest,
    db: Session = Depends(get_db),
):
    """
    从本地文件路径导入笔记

    流程: 验证路径 → 解析 → 创建 Note → 自动向量化

    Args:
        req.file_path: 本地文件绝对路径
        req.folder: 目标文件夹
        req.tags: 初始标签列表

    Returns:
        { "note": {...}, "synced": true }
    """
    file_path = Path(req.file_path)

    # ---- 1. 校验 ----
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"文件不存在: {req.file_path}")

    ext = file_path.suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的格式 '{ext}'，支持: {', '.join(sorted(SUPPORTED_EXTENSIONS))}",
        )

    file_size = file_path.stat().st_size
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if file_size > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"文件超过 {settings.max_upload_size_mb}MB 限制",
        )

    if file_size == 0:
        raise HTTPException(status_code=400, detail="文件内容为空")

    # ---- 2. 解析 ----
    try:
        parsed = await document_parser.parse_file(str(file_path))
    except DocumentParseError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"解析异常: {e}")
        raise HTTPException(status_code=500, detail=f"文档解析失败: {e}")

    if not parsed.content.strip():
        raise HTTPException(status_code=400, detail="解析后内容为空")

    # ---- 3. 创建笔记 ----
    note = await note_service.create(
        db,
        title=parsed.title,
        content=parsed.content,
        tags=req.tags,
    )

    note.folder = req.folder.strip()
    note.source_type = parsed.source_type
    note.source_path = str(file_path.resolve())  # 绝对路径
    note.content_hash = Note.compute_content_hash(parsed.content)
    note.word_count = parsed.word_count
    db.commit()
    db.refresh(note)

    # ---- 4. 自动向量化（note_service.create 已做，这里确认同步状态） ----
    synced = note.last_synced_at is not None
    if not synced:
        try:
            await rag_engine.index_note(note.id, note.title, note.content)
            from datetime import datetime, timezone
            note.last_synced_at = datetime.now(timezone.utc)
            note.content_hash = Note.compute_content_hash(parsed.content)
            db.commit()
            synced = True
        except Exception as e:
            logger.error(f"导入时向量化失败 — 笔记 {note.id}: {e}")

    return {
        "note": note.to_dict(include_content=True),
        "synced": synced,
    }
