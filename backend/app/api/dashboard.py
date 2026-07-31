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
DEFAULT_TOP_K = 3           # 每篇笔记默认连接的最强邻居数
MAX_EDGES = 200           # 全量边返回上限（悬停展示用，防止大数据量卡顿）
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


def _build_edges(
    embeddings: dict[int, list[float]],
    top_k: int,
    threshold: float,
) -> tuple[list[dict], list[dict]]:
    """
    基于 Embedding 余弦相似度构建连线（纯语义，用户约束）

    返回两组边:
      - edges:     每篇笔记只连语义最强的 top_k 个邻居（无向去重）
                   → 默认图稀疏（边数上限 ≈ N * top_k / 2），不杂乱
      - all_edges: 全部相似度 >= threshold 的边，供前端悬停节点时
                   临时亮出该节点的完整语义关联（超限取最强 Top-N）
    """
    if len(embeddings) < 2:
        return [], []

    ids = list(embeddings.keys())
    matrix = np.array([embeddings[nid] for nid in ids], dtype=float)

    # 归一化 → 余弦相似度 = 归一化向量的点积
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    matrix = matrix / norms
    sim = matrix @ matrix.T

    # ---- 收集所有 >= threshold 的无向边（权重表） ----
    n = len(ids)
    weights: dict[tuple[int, int], float] = {}
    for i in range(n):
        for j in range(i + 1, n):
            s = float(sim[i][j])
            if s >= threshold:
                weights[(ids[i], ids[j])] = round(s, 4)

    # ---- Top-K: 每个节点取相似度最强的 top_k 个邻居 ----
    neighbor_scores: dict[int, list[tuple[float, int]]] = {}
    for (a, b), w in weights.items():
        neighbor_scores.setdefault(a, []).append((w, b))
        neighbor_scores.setdefault(b, []).append((w, a))

    selected: set[tuple[int, int]] = set()
    for nid, lst in neighbor_scores.items():
        lst.sort(key=lambda x: x[0], reverse=True)
        for _, other in lst[:top_k]:
            selected.add((min(nid, other), max(nid, other)))

    edges = [
        {"source": a, "target": b, "weight": weights[(a, b)]}
        for a, b in sorted(selected)
    ]

    # ---- 全量边（悬停展示用） ----
    all_edges = [
        {"source": a, "target": b, "weight": w}
        for (a, b), w in sorted(weights.items(), key=lambda kv: kv[1], reverse=True)
    ]
    if len(all_edges) > MAX_EDGES:
        all_edges = all_edges[:MAX_EDGES]

    return edges, all_edges


@router.get("/graph")
async def dashboard_graph(
    notebook_id: int | None = Query(default=None, description="按笔记库筛选，默认全部"),
    threshold: float = Query(default=DEFAULT_THRESHOLD, ge=0.1, le=1.0, description="全量边相似度阈值"),
    top_k: int = Query(default=DEFAULT_TOP_K, ge=1, le=10, description="每篇笔记连接的最强邻居数"),
    db: Session = Depends(get_db),
):
    """
    知识图谱数据（语义互联 + Top-K 邻居）

    节点 = 每篇笔记。
    edges = 每篇笔记与其语义最强的 top_k 个邻居连线（默认稀疏，不杂乱）。
    all_edges = 全部相似度 >= threshold 的边（供前端悬停节点时展示完整关联）。
    标签仅作节点分类着色（category），不参与连线（用户明确约束）。

    Returns:
        {
          "nodes": [{"id", "name", "category", "symbolSize", "word_count", "notebook_id", "folder", "tags"}],
          "edges": [{"source", "target", "weight"}],
          "all_edges": [{"source", "target", "weight"}]
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
    edges, all_edges = _build_edges(scope_embeddings, top_k, threshold)

    logger.info(
        f"图谱数据: {len(nodes)} 节点, {len(edges)} 条 Top-K 边, "
        f"{len(all_edges)} 条全量边 "
        f"(threshold={threshold}, top_k={top_k}, notebook_id={notebook_id})"
    )
    return {"nodes": nodes, "edges": edges, "all_edges": all_edges}
