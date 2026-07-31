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

import json
import logging
from collections import defaultdict

import numpy as np
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.note import Note
from app.models.note_link import NoteLink
from app.models.tag import Tag
from app.core.rag_engine import rag_engine
from app.core.llm import llm_service
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


def _build_cluster_edges(
    ids: list[int],
    sim: np.ndarray,
    components: dict[int, int],
    top_per_cluster: int = 2,
    min_sim: float = 0.30,
) -> list[dict]:
    """
    簇间相似度 → 相关云朵连线（每簇连它最相似的 top_per_cluster 个簇，无向去重）
    weight = 两簇全部笔记两两相似度的均值，用于云朵连线的粗细。
    """
    members: dict[int, list[int]] = defaultdict(list)
    for nid in ids:
        members[components[nid]].append(nid)
    clusters = list(members.keys())
    idx = {nid: i for i, nid in enumerate(ids)}

    weights: dict[tuple[int, int], float] = {}
    for i, c1 in enumerate(clusters):
        for j in range(i + 1, len(clusters)):
            c2 = clusters[j]
            total = 0.0
            cnt = 0
            for a in members[c1]:
                for b in members[c2]:
                    total += float(sim[idx[a]][idx[b]])
                    cnt += 1
            # 键统一为 (小, 大)，避免簇编号顺序影响查找
            key = (min(c1, c2), max(c1, c2))
            weights[key] = total / max(cnt, 1)

    cands: dict[int, list[tuple[float, int]]] = defaultdict(list)
    for (a, b), w in weights.items():
        if w < min_sim:
            continue
        cands[a].append((w, b))
        cands[b].append((w, a))

    selected: set[tuple[int, int]] = set()
    for c, lst in cands.items():
        lst.sort(key=lambda x: x[0], reverse=True)
        for _, other in lst[:top_per_cluster]:
            selected.add((min(c, other), max(c, other)))

    return [
        {"source": a, "target": b, "weight": round(weights[(a, b)], 4)}
        for a, b in sorted(selected)
    ]


def _build_graph(
    embeddings: dict[int, list[float]],
    top_k: int,
    threshold: float,
    clusters: int | None,
) -> tuple[list[dict], dict[int, int], dict[int, int]]:
    """
    基于 Embedding 余弦相似度构建关联结构（纯语义，用户约束）

    Returns:
      - edges:        每篇笔记的 Top-K 强关联邻居（用于点击高亮）
      - degree:       笔记 → 强关联次数（决定节点大小/重要性）
      - components:   笔记 → KMeans 簇编号（同簇进同一朵云）
      - cluster_edges: 簇间相似度边（相关云朵互联，weight=两簇笔记相似度均值）
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

    # ---- KMeans 语义分簇（同一簇进同一朵云） ----
    n_clusters = clusters if clusters else max(
        MIN_CLUSTERS, min(round(np.sqrt(n)), MAX_CLUSTERS)
    )
    components = _kmeans_clusters(ids, matrix, n_clusters)
    cluster_edges = _build_cluster_edges(ids, sim, components)

    return edges, degree, components, cluster_edges


def _build_nodes(
    db: Session,
    degree: dict[int, int],
    components: dict[int, int],
) -> list[dict]:
    """构建节点（同簇进同一朵云，关联次数决定大小）"""
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
            "cluster_id": comp,  # None = 未进任何云朵（游离节点）
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
    知识图谱数据（云朵语义聚类，不画内部连线）

    节点 = 每篇笔记。
    - cluster_id  = KMeans 簇编号（同簇进同一朵云）
    - symbolSize  = 强关联次数（被多少篇笔记强关联，越多越大 = 越重要）
    - degree      = 强关联次数（tooltip 展示）
    edges = Top-K 强关联邻居（点击节点时高亮这些关联笔记）。
    clusters = 簇信息（id / 数量 / 标题 / 内容摘要，供 Agent 命名云朵）。
    cluster_edges = 簇间相似度边（相关云朵互联，weight=两簇笔记相似度均值）。

    Returns:
        {
          "nodes": [{"id", "name", "category", "symbolSize", "degree", "cluster_id", "word_count", "notebook_id", "folder", "tags"}],
          "edges": [{"source", "target", "weight"}],
          "clusters": [{"cluster_id", "count", "titles", "preview"}],
          "cluster_edges": [{"source", "target", "weight"}]
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
    edges, degree, components, cluster_edges = _build_graph(
        scope_embeddings, top_k, threshold, clusters
    )
    nodes = _build_nodes(db, degree, components)

    # ---- 簇信息（标题 + 内容摘要，供前端给 Agent 命名云朵） ----
    members: dict[int, list[int]] = defaultdict(list)
    for nid, c in components.items():
        members[c].append(nid)
    cluster_list: list[dict] = []
    if members:
        all_note_ids = [nid for nids in members.values() for nid in nids]
        note_by_id: dict[int, Note] = {}
        for note in db.query(Note).filter(Note.id.in_(all_note_ids)).all():
            note_by_id[note.id] = note
        for c in sorted(members.keys()):
            notes = [note_by_id[nid] for nid in members[c] if nid in note_by_id]
            if not notes:
                continue
            titles = [n.title or "无标题" for n in notes][:8]
            preview = " | ".join(
                (n.content or "").replace("\n", " ")[:80] for n in notes
            )[:400]
            cluster_list.append({
                "cluster_id": c,
                "count": len(notes),
                "titles": titles,
                "preview": preview,
            })
        cluster_list.sort(key=lambda x: x["count"], reverse=True)

    logger.info(
        f"图谱数据: {len(nodes)} 节点, {len(edges)} 条内部边, "
        f"{len(cluster_list)} 簇, {len(cluster_edges)} 条簇间连线 "
        f"(threshold={threshold}, top_k={top_k}, notebook_id={notebook_id})"
    )
    return {
        "nodes": nodes,
        "edges": edges,
        "clusters": cluster_list,
        "cluster_edges": cluster_edges,
    }


# ============================================================
# 云朵命名（Agent 调用 LLM 总结每簇主题）
# ============================================================

class ClusterNamingItem(BaseModel):
    cluster_id: int
    titles: list[str] = []
    preview: str = ""


class ClusterNamesRequest(BaseModel):
    clusters: list[ClusterNamingItem]


CLUSTER_NAMING_SYSTEM_PROMPT = """你是个人知识库整理助手。系统会提供若干「笔记簇」，每簇由多篇笔记的标题和内容片段组成，它们语义相近。
请为每一簇起一个简洁、具体、能概括该簇共同主题的名称（2~6 个汉字）。
要求：
1. 名称要具体可区分，避免「学习笔记」「资料汇总」「文档」这类泛泛的词
2. 不同簇的名称不能重复
3. 只输出 JSON，不要任何解释或其它文字，格式严格如下：
{"names": [{"cluster_id": 1, "name": "示例名称"}]}"""


def _parse_cluster_names(reply: str, clusters: list[ClusterNamingItem]) -> list[dict]:
    """解析 LLM 返回的簇名 JSON（容忍 ``` 代码块包裹）"""
    text = reply.strip()
    if text.startswith("```"):
        parts = text.split("```", 2)
        text = parts[1] if len(parts) > 1 else text
        if text.startswith("json"):
            text = text[4:].lstrip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("LLM 未返回 JSON 对象")
    data = json.loads(text[start:end + 1])
    by_id = {
        int(item["cluster_id"]): str(item["name"]).strip()
        for item in data.get("names", [])
    }
    return [
        {"cluster_id": c.cluster_id, "name": by_id.get(c.cluster_id) or f"簇{c.cluster_id}"}
        for c in clusters
    ]


@router.post("/cluster-names")
async def dashboard_cluster_names(req: ClusterNamesRequest):
    """
    为每个簇（云朵）生成语义名称（Agent 调用 LLM，根据簇内笔记内容总结）
    LLM 失败时降级为「簇N」，不阻塞前端。
    """
    if not req.clusters:
        return {"names": []}

    payload = json.dumps(
        [
            {"cluster_id": c.cluster_id, "titles": c.titles, "preview": c.preview}
            for c in req.clusters
        ],
        ensure_ascii=False,
    )
    try:
        reply = await llm_service.chat(
            messages=[
                {"role": "system", "content": CLUSTER_NAMING_SYSTEM_PROMPT},
                {"role": "user", "content": payload},
            ],
            temperature=0.3,
            max_tokens=400,
        )
        names = _parse_cluster_names(reply, req.clusters)
        logger.info(f"云朵命名完成: {len(names)} 个簇")
    except Exception as e:
        logger.error(f"云朵命名失败，降级为簇N: {e}")
        names = [{"cluster_id": c.cluster_id, "name": f"簇{c.cluster_id}"} for c in req.clusters]
    return {"names": names}
