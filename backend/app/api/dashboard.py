"""
数据看板 API（P7）
-----------------
GET /api/dashboard/stats — 统计概览（笔记/标签/链接/同步）
GET /api/dashboard/graph — 知识图谱数据（语义聚类，用户约束: 不画连线）

图谱设计（用户明确要求）:
  - 不画连线，靠「颜色 + 位置 + 大小」表达关联
  - 关联 = Embedding 余弦相似度 >= threshold
  - 同一连通簇（相互关联）→ 相同颜色（category = 簇N）
  - 关联次数（被多少篇笔记关联）越多 → 节点越大（symbolSize）
  - edges 仅用于力导向布局聚簇 + 点击高亮（前端隐藏，不绘制）
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
DEFAULT_THRESHOLD = 0.62       # 相似度 >= 此值视为「强关联」（用于关联次数 + 布局边）
DEFAULT_TOP_K = 4              # 每篇笔记用于布局/高亮的最近邻居数
DEFAULT_CLUSTERS = None        # 簇数（None = 按 sqrt(笔记数) 启发式）
MIN_CLUSTERS = 2
MAX_CLUSTERS = 12
# 节点大小 = 基础 + 关联次数缩放（关联越多 = 越重要 = 越大）
BASE_SYMBOL = 14
DEGREE_SCALE = 5               # 每多 1 篇关联 +5
SIZE_CAP = 50


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
# 知识图谱（语义聚类，不画连线）
# ============================================================

def _kmeans_clusters(
    ids: list[int],
    matrix: np.ndarray,
    n_clusters: int,
    seed: int = 42,
) -> dict[int, int]:
    """
    基于 Embedding 的 KMeans 聚类（纯 numpy，k-means++ 初始化，固定种子可复现）

    数据中笔记普遍语义相近（bge 向量相似度高），绝对阈值分不开簇，
    因此用 KMeans 把笔记分成语义组：同簇同色。

    Returns:
        笔记 → 簇编号（按簇大小降序编号，簇1 最大，稳定可复现）
    """
    n = len(ids)
    k = max(1, min(n_clusters, n))
    if k <= 1:
        return {nid: 1 for nid in ids}

    rng = np.random.RandomState(seed)
    centers = np.zeros((k, matrix.shape[1]))

    # k-means++ 初始化
    centers[0] = matrix[rng.randint(n)]
    for c in range(1, k):
        dist = ((matrix[:, None, :] - centers[None, :c, :]) ** 2).sum(axis=2).min(axis=1)
        probs = dist / dist.sum()
        centers[c] = matrix[rng.choice(n, p=probs)]

    labels = np.zeros(n, dtype=int)
    for _ in range(50):
        new_labels = (
            (matrix[:, None, :] - centers[None, :, :]) ** 2
        ).sum(axis=2).argmin(axis=1)
        for c in range(k):
            members = matrix[new_labels == c]
            if len(members):
                centers[c] = members.mean(axis=0)
        if np.array_equal(new_labels, labels):
            break
        labels = new_labels

    # 按簇大小降序编号，保证 簇1 最大且稳定
    unique, counts = np.unique(labels, return_counts=True)
    order = unique[np.argsort(-counts)]
    rank = {int(u): i + 1 for i, u in enumerate(order)}
    return {ids[i]: rank[int(labels[i])] for i in range(n)}


def _build_graph(
    embeddings: dict[int, list[float]],
    top_k: int,
    threshold: float,
    clusters: int | None,
) -> tuple[list[dict], dict[int, int], dict[int, int]]:
    """
    基于 Embedding 余弦相似度构建关联结构（纯语义，用户约束）

    Returns:
      - edges:      每篇笔记的 Top-K 强关联邻居（仅用于力导向布局 + 点击高亮，前端隐藏连线）
      - degree:     笔记 → 强关联次数（决定节点大小/重要性）
      - components: 笔记 → KMeans 簇编号（同簇同色，KMeans 解决「全笔记都相近」分不开的问题）
    """
    if len(embeddings) < 2:
        return [], {}, {}

    ids = list(embeddings.keys())
    matrix = np.array([embeddings[nid] for nid in ids], dtype=float)

    # 归一化 → 余弦相似度 = 归一化向量的点积
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    matrix = matrix / norms
    sim = matrix @ matrix.T

    # ---- 强关联（相似度 >= threshold 才视为关联） ----
    n = len(ids)
    weights: dict[tuple[int, int], float] = {}
    for i in range(n):
        for j in range(i + 1, n):
            s = float(sim[i][j])
            if s >= threshold:
                weights[(ids[i], ids[j])] = round(s, 4)

    # ---- 关联次数（重要性） ----
    degree: dict[int, int] = {nid: 0 for nid in ids}
    for (a, b) in weights:
        degree[a] += 1
        degree[b] += 1

    # ---- Top-K 邻居边（布局 + 高亮用） ----
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

    # ---- KMeans 语义分簇（颜色分组） ----
    n_clusters = clusters if clusters else max(
        MIN_CLUSTERS, min(round(np.sqrt(n)), MAX_CLUSTERS)
    )
    components = _kmeans_clusters(ids, matrix, n_clusters)

    return edges, degree, components


def _build_nodes(
    db: Session,
    degree: dict[int, int],
    components: dict[int, int],
) -> list[dict]:
    """构建节点（同簇同色，关联次数决定大小）"""
    notes = db.query(Note).order_by(Note.updated_at.desc()).all()
    nodes: list[dict] = []
    for note in notes:
        tag_names = [t.name for t in note.tags] if note.tags else []
        comp = components.get(note.id)
        category = f"簇{comp}" if comp is not None else "未关联"
        d = degree.get(note.id, 0)
        symbol = BASE_SYMBOL + min(d * DEGREE_SCALE, SIZE_CAP - BASE_SYMBOL)
        nodes.append({
            "id": note.id,
            "name": note.title or "无标题",
            "category": category,
            "symbolSize": round(symbol, 1),
            "degree": d,
            "word_count": note.word_count or 0,
            "notebook_id": note.notebook_id,
            "folder": note.folder or "",
            "tags": tag_names,
        })
    return nodes


@router.get("/graph")
async def dashboard_graph(
    notebook_id: int | None = Query(default=None, description="按笔记库筛选，默认全部"),
    threshold: float = Query(default=DEFAULT_THRESHOLD, ge=0.1, le=1.0, description="相似度 >= 此值视为强关联"),
    top_k: int = Query(default=DEFAULT_TOP_K, ge=1, le=10, description="每篇笔记的语义邻居数（布局/高亮）"),
    clusters: int | None = Query(default=DEFAULT_CLUSTERS, ge=MIN_CLUSTERS, le=MAX_CLUSTERS, description="簇数（默认按 sqrt(笔记数) 启发式）"),
    db: Session = Depends(get_db),
):
    """
    知识图谱数据（语义聚类，不画连线）

    节点 = 每篇笔记。
    - category    = KMeans 簇编号（同簇 = 语义相近，同色；解决「笔记普遍相近」绝对阈值分不开的问题）
    - symbolSize  = 强关联次数（被多少篇笔记强关联，越多越大 = 越重要）
    - degree      = 强关联次数（tooltip 展示）
    edges = Top-K 强关联邻居，仅用于力导向布局聚簇 + 点击高亮（前端隐藏连线）。

    Returns:
        {
          "nodes": [{"id", "name", "category", "symbolSize", "degree", "word_count", "notebook_id", "folder", "tags"}],
          "edges": [{"source", "target", "weight"}]
        }
    """
    # 只取本笔记库的节点计算关联（范围过滤）
    if notebook_id:
        keep_ids = set()
        for (note_id,) in db.query(Note.id).filter(Note.notebook_id == notebook_id).all():
            keep_ids.add(note_id)
    else:
        keep_ids = {nid for (nid,) in db.query(Note.id).all()}

    embeddings = rag_engine.get_all_embeddings()
    scope_embeddings = {
        nid: vec for nid, vec in embeddings.items()
        if nid in keep_ids
    }
    edges, degree, components = _build_graph(scope_embeddings, top_k, threshold, clusters)
    nodes = _build_nodes(db, degree, components)

    logger.info(
        f"图谱数据: {len(nodes)} 节点, {len(edges)} 条布局边, {len(set(components.values()))} 簇 "
        f"(threshold={threshold}, top_k={top_k}, clusters={clusters}, notebook_id={notebook_id})"
    )
    return {"nodes": nodes, "edges": edges}
