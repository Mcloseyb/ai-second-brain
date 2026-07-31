"""
数据看板 API（P7）
-----------------
GET /api/dashboard/stats — 统计概览（笔记/标签/链接/同步）
GET /api/dashboard/graph — 知识图谱数据（语义互联驱动）

图谱连线完全基于笔记 Embedding 余弦相似度（用户约束: 不靠标签互联）。
标签仅作为节点分类着色，不参与连线。
"""

import logging

import numpy as np
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.note import Note
from app.models.note_link import NoteLink
from app.models.tag import Tag
from app.core.rag_engine import rag_engine
from app.services.sync_service import sync_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

# 图谱默认参数
DEFAULT_THRESHOLD = 0.35
MAX_EDGES = 200           # 最多返回边数（超出取最强 Top-N，防前端卡顿）
MIN_SYMBOL = 12           # 无 embedding 的孤点大小
# 节点大小 = 基础 18 + 字数缩放，乘引用度系数
BASE_SYMBOL = 18
WORD_SCALE = 1 / 100      # 每 100 字 +1
WORD_CAP = 30             # 字数对大小贡献上限
REF_SCALE = 6             # 每个引用 +6


# ============================================================
# 统计概览
# ============================================================

@router.get("/stats")
async def dashboard_stats(db: Session = Depends(get_db)):
    """
    数据看板统计

    Returns:
        {
          "total_notes": 9, "total_tags": 4,
          "total_links": 5, "synced": 9, "pending": 0
        }
    """
    total_notes = db.query(Note).count()
    total_tags = db.query(Tag).count()
    total_links = db.query(NoteLink).count()

    sync = sync_service.get_status(db)

    return {
        "total_notes": total_notes,
        "total_tags": total_tags,
        "total_links": total_links,
        "synced": sync["synced"],
        "pending": sync["pending"],
    }


# ============================================================
# 知识图谱（语义互联）
# ============================================================

def _ref_counts(db: Session) -> dict[int, int]:
    """计算每篇笔记被引用的次数（note_links.target_note_id 计数）"""
    counts: dict[int, int] = {}
    for (target,) in db.query(NoteLink.target_note_id).all():
        counts[target] = counts.get(target, 0) + 1
    return counts


def _build_nodes(db: Session, refs: dict[int, int]) -> list[dict]:
    """构建节点列表（每篇笔记一个节点）"""
    notes = db.query(Note).order_by(Note.updated_at.desc()).all()
    nodes: list[dict] = []
    for note in notes:
        tag_names = [t.name for t in note.tags] if note.tags else []
        category = tag_names[0] if tag_names else "未分类"
        word_size = min((note.word_count or 0) * WORD_SCALE, WORD_CAP)
        symbol_size = BASE_SYMBOL + word_size + refs.get(note.id, 0) * REF_SCALE
        nodes.append({
            "id": note.id,
            "name": note.title or "无标题",
            "category": category,
            "symbolSize": round(min(symbol_size, 80), 1),
            "word_count": note.word_count or 0,
            "notebook_id": note.notebook_id,
            "folder": note.folder or "",
            "tags": tag_names,
        })
    return nodes


def _build_edges(embeddings: dict[int, list[float]], threshold: float) -> list[dict]:
    """
    基于 Embedding 余弦相似度构建连线（纯语义，用户约束）

    一次性向量矩阵 → numpy 余弦相似度 → 过滤阈值 + 排除自身 + 去重。
    """
    if len(embeddings) < 2:
        return []

    ids = list(embeddings.keys())
    id_to_idx = {nid: i for i, nid in enumerate(ids)}
    matrix = np.array([embeddings[nid] for nid in ids], dtype=float)

    # 归一化 → 余弦相似度 = 归一化向量的点积
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    matrix = matrix / norms
    sim = matrix @ matrix.T

    edges: list[dict] = []
    n = len(ids)
    for i in range(n):
        for j in range(i + 1, n):
            s = float(sim[i][j])
            if s >= threshold:
                edges.append({
                    "source": ids[i],
                    "target": ids[j],
                    "weight": round(s, 4),
                })

    # 超限 → 取 Top-N 最强边
    if len(edges) > MAX_EDGES:
        edges.sort(key=lambda e: e["weight"], reverse=True)
        edges = edges[:MAX_EDGES]

    return edges


@router.get("/graph")
async def dashboard_graph(
    notebook_id: int | None = Query(default=None, description="按笔记库筛选，默认全部"),
    threshold: float = Query(default=DEFAULT_THRESHOLD, ge=0.1, le=1.0, description="语义相似度阈值"),
    db: Session = Depends(get_db),
):
    """
    知识图谱数据（语义互联）

    节点 = 每篇笔记；边 = 两篇笔记 Embedding 余弦相似度 >= 阈值。
    标签仅作节点分类着色（category），不参与连线（用户明确约束）。

    Returns:
        {
          "nodes": [{"id", "name", "category", "symbolSize", "word_count", "notebook_id", "folder", "tags"}],
          "edges": [{"source", "target", "weight"}]
        }
    """
    refs = _ref_counts(db)
    nodes = _build_nodes(db, refs)

    # 只取本笔记库的节点计算边（排除自身之外的索引）
    if notebook_id:
        keep_ids = {n["id"] for n in nodes if n["notebook_id"] == notebook_id}
    else:
        keep_ids = {n["id"] for n in nodes}

    embeddings = rag_engine.get_all_embeddings()
    # 只保留范围内且非空向量的笔记
    scope_embeddings = {
        nid: vec for nid, vec in embeddings.items()
        if nid in keep_ids
    }
    edges = _build_edges(scope_embeddings, threshold)

    logger.info(
        f"图谱数据: {len(nodes)} 节点, {len(edges)} 条边 "
        f"(threshold={threshold}, notebook_id={notebook_id})"
    )
    return {"nodes": nodes, "edges": edges}
