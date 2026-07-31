"""
笔记 API — CRUD + 语义搜索
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.note_service import note_service
from app.core.rag_engine import rag_engine

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


class NoteSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000, description="自然语言搜索查询")
    top_k: int = Field(default=5, ge=1, le=20, description="返回结果数量")
    threshold: float = Field(default=0.0, ge=0.0, le=1.0, description="相似度阈值")


# ============================================================
# Endpoints
# ============================================================

@router.post("", status_code=201)
async def create_note(data: NoteCreate, db: Session = Depends(get_db)):
    """创建笔记"""
    note = await note_service.create(db, title=data.title, content=data.content, tags=data.tags)
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
    note = await note_service.update(
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
    ok = await note_service.delete(db, note_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Note not found")
    return {"ok": True}


# ============================================================
# 语义搜索（P3.2.1）
# ============================================================

@router.post("/search")
async def search_notes(data: NoteSearchRequest, db: Session = Depends(get_db)):
    """
    语义搜索笔记 — 用自然语言查找最相关的笔记

    基于 ChromaDB 向量相似度检索，返回 Top-K 条匹配结果，
    包含匹配片段和相似度分数。

    Args:
        query: 自然语言搜索查询，如 "关于 Transformer 注意力机制的笔记"
        top_k: 返回结果数量 (1-20)
        threshold: 相似度阈值 (0.0-1.0)，低于此值的结果会被过滤

    Returns:
        { "results": [{note_id, title, text, similarity}, ...], "query": "..." }
    """
    results = await rag_engine.search(
        query=data.query,
        top_k=data.top_k,
        threshold=data.threshold,
    )

    # 补充笔记元数据（folder、tags 等）
    enriched = []
    for r in results:
        note = note_service.get_by_id(db, r["note_id"])
        enriched.append({
            "note_id": r["note_id"],
            "title": r["title"],
            "text": r["text"],          # 匹配片段（存储的前 2000 字符）
            "similarity": r["similarity"],
            "folder": note.folder if note else "",
            "tags": [t.to_dict() for t in note.tags] if note else [],
            "word_count": note.word_count if note else 0,
            "updated_at": note.updated_at.isoformat() if note and note.updated_at else None,
        })

    return {
        "results": enriched,
        "query": data.query,
    }
