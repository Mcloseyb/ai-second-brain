"""
笔记 API — CRUD + 语义搜索
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.note_service import note_service
from app.services.link_service import link_service
from app.core.rag_engine import rag_engine
from app.agents.tag_agent import tag_agent

router = APIRouter(prefix="/api/notes", tags=["notes"])


# ============================================================
# Schema
# ============================================================

class NoteCreate(BaseModel):
    title: str = Field(default="Untitled", max_length=500)
    content: str = Field(default="")
    tags: list[str] = Field(default_factory=list)
    notebook_id: int | None = Field(default=None, description="所属笔记库 ID")
    folder: str = Field(default="", description="文件夹路径，如 AI/Agent")


class NoteUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=500)
    content: str | None = None
    tags: list[str] | None = None


class NoteSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000, description="自然语言搜索查询")
    top_k: int = Field(default=5, ge=1, le=20, description="返回结果数量")
    threshold: float = Field(default=0.0, ge=0.0, le=1.0, description="相似度阈值")
    hybrid: bool = Field(default=True, description="是否启用混合检索(semantic+BM25)，False 则纯语义")


class SuggestTagsRequest(BaseModel):
    """为尚未创建的笔记内容推荐标签（导入对话框用）"""
    title: str = Field(default="", max_length=500)
    content: str = Field(default="", max_length=100000)


# ============================================================
# Endpoints
# ============================================================

@router.post("", status_code=201)
async def create_note(data: NoteCreate, db: Session = Depends(get_db)):
    """创建笔记"""
    note = await note_service.create(
        db,
        title=data.title,
        content=data.content,
        tags=data.tags,
        notebook_id=data.notebook_id,
        folder=data.folder,
    )
    return {"note": note.to_dict()}


@router.get("")
async def list_notes(
    search: str | None = Query(default=None, description="搜索关键词"),
    tag: str | None = Query(default=None, description="按标签筛选"),
    notebook_id: int | None = Query(default=None, description="按笔记库筛选"),
    folder: str | None = Query(default=None, description="按文件夹筛选"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """笔记列表（分页 + 搜索 + 筛选）"""
    notes, total = note_service.list_notes(
        db,
        search=search,
        tag=tag,
        notebook_id=notebook_id,
        folder=folder,
        page=page,
        page_size=page_size,
    )
    return {
        "notes": [n.to_dict(include_content=False) for n in notes],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


# ============================================================
# 回收站（Trash）— 必须在 /{note_id} 之前注册，避免路由冲突
# ============================================================

@router.get("/trash")
async def list_trash(
    notebook_id: int | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """回收站列表"""
    notes, total = await note_service.trash_list(db, notebook_id, page, page_size)
    return {
        "notes": [n.to_dict(include_content=False) for n in notes],
        "total": total, "page": page, "page_size": page_size,
    }


@router.post("/{note_id}/restore")
async def restore_note(note_id: int, db: Session = Depends(get_db)):
    """从回收站恢复笔记"""
    note = await note_service.restore(db, note_id)
    if not note:
        raise HTTPException(status_code=404, detail="Note not found in trash")
    return {"note": note.to_dict()}


@router.delete("/{note_id}/permanent")
async def permanent_delete_note(note_id: int, db: Session = Depends(get_db)):
    """永久删除笔记（不可恢复）"""
    ok = await note_service.permanent_delete(db, note_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Note not found in trash")
    return {"ok": True}


@router.post("/trash/empty")
async def empty_trash(
    notebook_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """清空回收站"""
    count = await note_service.empty_trash(db, notebook_id)
    return {"ok": True, "deleted": count}


class FolderDeleteRequest(BaseModel):
    notebook_id: int
    folder: str


@router.post("/folder-delete")
async def delete_folder(req: FolderDeleteRequest, db: Session = Depends(get_db)):
    """删除文件夹及其内所有笔记（软删除）"""
    count = await note_service.delete_folder(db, req.notebook_id, req.folder)
    return {"ok": True, "deleted": count}


@router.get("/folder-count")
async def folder_note_count(
    notebook_id: int = Query(...),
    folder: str = Query(...),
    db: Session = Depends(get_db),
):
    """统计文件夹内笔记数量"""
    count = note_service.count_folder_notes(db, notebook_id, folder)
    return {"count": count}


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
    """删除笔记（软删除，移入回收站）"""
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
        hybrid=data.hybrid,
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


# ============================================================
# AI 自动标签推荐（P4 简易版: jieba TF-IDF + Embedding）
# ============================================================

@router.post("/{note_id}/auto-tag")
async def auto_tag_note(
    note_id: int,
    mode: str = Query(default="simple", pattern="^(simple|llm)$"),
    db: Session = Depends(get_db),
):
    """
    AI 自动标签推荐 — 根据笔记内容推荐标签（最多 3 个）

    mode 参数:
      - simple: 简易版（默认）— jieba TF-IDF + Embedding，零 LLM token
      - llm:    完整版 — Function Calling + LLM 决策（deepseek-chat, temp=0），
                可返回合并建议、创建新标签

    Returns (simple):
        {
          "note_id": 1, "mode": "simple",
          "suggestions": [
            {"tag": "深度学习", "type": "existing", "tag_id": 3,
             "keyword": "神经网络", "score": 0.82},
            {"tag": "transformer", "type": "new", "tag_id": null,
             "keyword": "transformer", "score": 0.62}
          ]
        }

    Returns (llm):
        在 simple 基础上增加 merge_suggestions（去重合并建议）与 steps（审计）。
    """
    note = note_service.get_by_id(db, note_id)
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")

    if mode == "llm":
        return await tag_agent.suggest_tags_llm(db, note)

    suggestions = await tag_agent.suggest_tags(db, note)
    return {"note_id": note_id, "mode": "simple", "suggestions": suggestions}


@router.post("/suggest-tags")
async def suggest_tags_content(req: SuggestTagsRequest, db: Session = Depends(get_db)):
    """
    为尚未创建的笔记内容推荐标签（导入对话框用：先推荐后导入）

    与 auto-tag 的 simple 版同逻辑（jieba TF-IDF + Embedding 语义匹配，零 token），
    但不需要先创建笔记。

    Returns:
        {"mode": "simple", "suggestions": [{tag, type, tag_id, keyword, score}, ...]}
    """
    suggestions = await tag_agent.suggest_tags_for_text(db, req.title, req.content)
    return {"mode": "simple", "suggestions": suggestions}


# ============================================================
# 智能双向链接（P5）
# ============================================================

class NoteLinksCreate(BaseModel):
    target_ids: list[int] = Field(default_factory=list, description="目标笔记 ID 列表")
    link_type: str = Field(default="title", pattern="^(title|manual)$", description="链接类型")


@router.get("/{note_id}/related")
async def related_notes(
    note_id: int,
    top_k: int = Query(default=5, ge=1, le=10),
    db: Session = Depends(get_db),
):
    """
    智能双向链接 — 返回与笔记语义最相关的 Top-K 笔记

    基于向量语义相似度（Embedding 余弦），实时计算、零 token。
    点击结果可跳转到对应笔记，形成"知识互联"。

    Returns:
        {"note_id": ..., "related": [{note_id, title, text, similarity, folder, tags}, ...]}
    """
    related = await link_service.get_related_notes(db, note_id, top_k=top_k)
    return {"note_id": note_id, "related": related}


@router.get("/{note_id}/linked-from")
async def linked_from_notes(note_id: int, db: Session = Depends(get_db)):
    """
    反向链接 — 引用此笔记的其他笔记（Linked from）

    基于 note_links 表的显式记录（标题检测 / 手动确认）。

    Returns:
        {"note_id": ..., "linked_from": [{id, title, folder, link_type, ...}, ...]}
    """
    linked_from = link_service.get_linked_from(db, note_id)
    return {"note_id": note_id, "linked_from": linked_from}


@router.get("/{note_id}/title-links")
async def title_links(note_id: int, db: Session = Depends(get_db)):
    """
    标题检测 — 扫描笔记正文，检测是否包含其他笔记的标题

    命中即"潜在引用"，前端展示建议，用户确认后通过 POST /links 落库。

    Returns:
        {"note_id": ..., "detections": [{target_note_id, title, count}, ...]}
    """
    detections = link_service.detect_title_links(db, note_id)
    return {"note_id": note_id, "detections": detections}


@router.post("/{note_id}/links", status_code=201)
async def create_links(
    note_id: int,
    data: NoteLinksCreate,
    db: Session = Depends(get_db),
):
    """
    记录显式链接 — 确认标题检测结果 / 手动添加链接

    Args:
        target_ids: 目标笔记 ID 列表
        link_type: title（自动检测确认）| manual（手动）

    Returns:
        {"recorded": n, "skipped": m}
    """
    note = note_service.get_by_id(db, note_id)
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    result = link_service.record_links(db, note_id, data.target_ids, data.link_type)
    return result
