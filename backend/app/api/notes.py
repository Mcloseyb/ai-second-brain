"""
笔记 API — CRUD 接口
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.note_service import note_service

router = APIRouter(prefix="/api/notes", tags=["notes"])


# ============================================================
# Schema
# ============================================================

class NoteCreate(BaseModel):
    title: str = Field(default="Untitled", max_length=500)
    content: str = Field(default="")
    tags: list[str] = Field(default_factory=list)


class NoteUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=500)
    content: str | None = None
    tags: list[str] | None = None


# ============================================================
# Endpoints
# ============================================================

@router.post("", status_code=201)
async def create_note(data: NoteCreate, db: Session = Depends(get_db)):
    """创建笔记"""
    note = note_service.create(db, title=data.title, content=data.content, tags=data.tags)
    return {"note": note.to_dict()}


@router.get("")
async def list_notes(
    search: str | None = Query(default=None, description="搜索关键词"),
    tag: str | None = Query(default=None, description="按标签筛选"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """笔记列表（分页 + 搜索 + 筛选）"""
    notes, total = note_service.list_notes(db, search=search, tag=tag, page=page, page_size=page_size)
    return {
        "notes": [n.to_dict(include_content=False) for n in notes],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/{note_id}")
async def get_note(note_id: int, db: Session = Depends(get_db)):
    """获取笔记详情"""
    note = note_service.get_by_id(db, note_id)
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    return {"note": note.to_dict(include_content=True)}


@router.put("/{note_id}")
async def update_note(note_id: int, data: NoteUpdate, db: Session = Depends(get_db)):
    """更新笔记"""
    note = note_service.update(
        db, note_id,
        title=data.title,
        content=data.content,
        tags=data.tags,
    )
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    return {"note": note.to_dict()}


@router.delete("/{note_id}")
async def delete_note(note_id: int, db: Session = Depends(get_db)):
    """删除笔记"""
    ok = note_service.delete(db, note_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Note not found")
    return {"ok": True}
