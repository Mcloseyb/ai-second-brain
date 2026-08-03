"""
聚类服务 — 温故知新
====================
从 dashboard.py (P7) 提取聚类逻辑，改为持久化到数据库。
支持：增量归类（新笔记自动归簇）+ 全量重聚类（用户手动触发 + Agent 命名）
"""

import json
import logging
from collections import defaultdict

import numpy as np
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.note import Note
from app.models.cluster import ConceptCluster, ClusterNote
from app.core.rag_engine import rag_engine
from app.core.llm import llm_service

logger = logging.getLogger(__name__)

# ── 聚类参数（复用 P7） ──────────────────────────────

DEFAULT_THRESHOLD = 0.62       # 相似度阈值 — 用于增量归簇和强关联判断
MIN_CLUSTERS = 2
MAX_CLUSTERS = 12

# ── Agent 命名 prompt（复用 P7） ──────────────────────

CLUSTER_NAMING_SYSTEM_PROMPT = """你是个人知识库整理助手。系统会提供若干「笔记簇」，每簇由多篇笔记的标题和内容片段组成，它们语义相近。
请为每一簇起一个简洁、具体、能概括该簇共同主题的名称（2~6 个汉字）。
要求：
1. 名称要具体可区分，避免「学习笔记」「资料汇总」「文档」这类泛泛的词
2. 不同簇的名称不能重复
3. 只输出 JSON，不要任何解释或其它文字，格式严格如下：
{"names": [{"cluster_id": 1, "name": "示例名称"}]}"""


# ── KMeans 聚类（从 dashboard.py 提取，纯 numpy，固定种子可复现） ──

def _kmeans_clusters(
    ids: list[int],
    matrix: np.ndarray,
    n_clusters: int,
    seed: int = 42,
) -> dict[int, int]:
    """
    KMeans 聚类（k-means++ 初始化，Lloyd 迭代，按簇大小降序编号）

    Returns:
        {note_id: cluster_number}  — cluster_number 1=最大簇
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

    # 按簇大小降序编号
    unique, counts = np.unique(labels, return_counts=True)
    order = unique[np.argsort(-counts)]
    rank = {int(u): i + 1 for i, u in enumerate(order)}
    return {ids[i]: rank[int(labels[i])] for i in range(n)}


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """两个向量之间的余弦相似度"""
    a_arr = np.array(a, dtype=float)
    b_arr = np.array(b, dtype=float)
    na, nb = np.linalg.norm(a_arr), np.linalg.norm(b_arr)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a_arr, b_arr) / (na * nb))


# ── ClusterService ──────────────────────────────────

class ClusterService:
    """概念簇管理 — 聚类 + 命名 + 持久化"""

    # ─── 增量归类：新笔记归入最近簇 ─────────────────

    def assign_note_to_cluster(self, db: Session, note_id: int) -> int | None:
        """
        为新导入的笔记找到最相似的簇并加入；相似度不够则返回 None。
        同时更新簇的中心向量（均值移动）。
        """
        # 获取笔记 embedding
        embeddings = rag_engine.get_all_embeddings()
        note_vec = embeddings.get(note_id)
        if not note_vec:
            logger.warning(f"笔记 {note_id} 无 embedding，跳过归簇")
            return None

        clusters = db.query(ConceptCluster).all()
        if not clusters:
            logger.info("尚无任何簇，笔记暂不归簇")
            return None

        best_cluster = None
        best_sim = -1.0
        for cluster in clusters:
            center = cluster.get_embedding()
            if not center:
                continue
            sim = _cosine_similarity(note_vec, center)
            if sim > best_sim:
                best_sim = sim
                best_cluster = cluster

        if best_cluster is None or best_sim < DEFAULT_THRESHOLD:
            logger.info(f"笔记 {note_id} 与最相似簇的相似度 {best_sim:.3f} < {DEFAULT_THRESHOLD}，暂不归簇")
            return None

        # 加入簇
        existing = db.query(ClusterNote).filter_by(note_id=note_id).first()
        if existing:
            if existing.cluster_id == best_cluster.id:
                return best_cluster.id
            # 从旧簇移除
            db.delete(existing)

        db.add(ClusterNote(cluster_id=best_cluster.id, note_id=note_id))

        # 更新簇的 note_count 和中心向量
        best_cluster.note_count = (
            db.query(ClusterNote).filter_by(cluster_id=best_cluster.id).count() + 1
        )
        self._update_cluster_center(db, best_cluster, embeddings)

        db.commit()
        logger.info(f"笔记 {note_id} 归入簇「{best_cluster.name}」(id={best_cluster.id}, sim={best_sim:.3f})")
        return best_cluster.id

    # ─── 全量重聚类 ─────────────────────────────────

    async def recluster_all(self, db: Session, notebook_id: int, seed: int = 42) -> dict:
        """
        全量重聚类：
        1. 从 ChromaDB 拉取全量 embedding
        2. 归一化 → KMeans → 写入 concept_clusters + cluster_notes
        3. Agent 命名新簇
        4. 返回簇列表

        注意: 会删除旧簇数据（SM-2 状态绑定笔记不变，不受影响）
        """
        # 1. 获取该笔记库的所有笔记 embedding
        all_embeddings = rag_engine.get_all_embeddings()
        notes = db.query(Note).filter(
            Note.notebook_id == notebook_id,
            Note.deleted_at.is_(None),
        ).all()

        note_ids = []
        vectors = []
        for note in notes:
            vec = all_embeddings.get(note.id)
            if vec is not None:
                note_ids.append(note.id)
                vectors.append(vec)

        if len(note_ids) < 2:
            logger.warning(f"笔记数不足 ({len(note_ids)}), 无法聚类")
            return {"clusters": [], "note_count": len(note_ids)}

        # 2. 归一化 → KMeans
        matrix = np.array(vectors, dtype=float)
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        matrix = matrix / norms

        n_clusters = max(MIN_CLUSTERS, min(round(np.sqrt(len(note_ids))), MAX_CLUSTERS))
        components = _kmeans_clusters(note_ids, matrix, n_clusters, seed=seed)

        # 3. 删除旧簇
        old_clusters = db.query(ConceptCluster).filter_by(notebook_id=notebook_id).all()
        for oc in old_clusters:
            db.query(ClusterNote).filter_by(cluster_id=oc.id).delete()
            db.delete(oc)
        db.commit()

        # 4. 写入新簇
        # 按簇编号分组笔记
        cluster_notes_map: dict[int, list[int]] = defaultdict(list)
        for nid, cnum in components.items():
            cluster_notes_map[cnum].append(nid)

        # 计算簇的元信息（标题 + 内容片段，供 Agent 命名）
        clusters_info = []
        note_map = {n.id: n for n in notes}

        for cnum in sorted(cluster_notes_map.keys()):
            member_ids = cluster_notes_map[cnum]
            member_vecs = [all_embeddings[nid] for nid in member_ids
                          if all_embeddings.get(nid)]

            # 计算中心向量
            if member_vecs:
                center = np.mean(member_vecs, axis=0).tolist()
            else:
                center = None

            cluster = ConceptCluster(
                notebook_id=notebook_id,
                name=f"簇{cnum}",    # 占位名，Agent 随后命名
                note_count=len(member_ids),
            )
            if center is not None:
                cluster.set_embedding(center)
            db.add(cluster)
            db.flush()  # 获取 cluster.id

            # 写入 cluster_notes 映射
            for nid in member_ids:
                db.add(ClusterNote(cluster_id=cluster.id, note_id=nid))

            # 收集标题和内容片段供 Agent 命名
            titles = []
            preview_parts = []
            for nid in member_ids[:8]:  # 最多 8 篇
                note = note_map.get(nid)
                if note:
                    titles.append(note.title or "无标题")
                    if note.content:
                        # 取前 80 字
                        clean = note.content.replace("\n", " ").strip()
                        preview_parts.append(clean[:80])
            preview = " | ".join(preview_parts)[:400]

            clusters_info.append({
                "cluster_id": cnum,
                "db_id": cluster.id,
                "titles": titles,
                "preview": preview,
            })

        db.commit()
        logger.info(f"重聚类完成: {len(cluster_notes_map)} 个簇, {len(note_ids)} 篇笔记")

        # 5. Agent 命名
        await self._name_clusters(clusters_info)

        # 6. 写回命名结果
        name_map = {c["db_id"]: c.get("name", f"簇{c['cluster_id']}") for c in clusters_info}
        for db_id, name in name_map.items():
            db.query(ConceptCluster).filter_by(id=db_id).update({"name": name})
        db.commit()

        return {
            "clusters": [
                {"id": c["db_id"], "name": name_map.get(c["db_id"], ""),
                 "note_count": cluster_notes_map[c["cluster_id"]]}
                for c in clusters_info
            ],
            "note_count": len(note_ids),
        }

    # ─── Agent 命名（复用 P7 prompt） ────────────────

    async def _name_clusters(self, clusters_info: list[dict]) -> None:
        """调用 LLM 给每个簇命名，结果写回 clusters_info（修改 db_id → name）"""
        if not clusters_info:
            return

        payload = json.dumps(
            [
                {"cluster_id": c["cluster_id"], "titles": c["titles"], "preview": c["preview"]}
                for c in clusters_info
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
            names = self._parse_cluster_names(reply, clusters_info)
            for item in clusters_info:
                item["name"] = names.get(item["cluster_id"], f"簇{item['cluster_id']}")
            logger.info(f"Agent 命名完成: {len(names)} 个簇")
        except Exception as e:
            logger.error(f"Agent 命名失败，使用 fallback: {e}")
            for item in clusters_info:
                item["name"] = f"簇{item['cluster_id']}"

    @staticmethod
    def _parse_cluster_names(reply: str, clusters_info: list[dict]) -> dict[int, str]:
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
        return {
            int(item["cluster_id"]): str(item["name"]).strip()
            for item in data.get("names", [])
        }

    # ─── 簇列表/详情 ────────────────────────────────

    def get_clusters(self, db: Session, notebook_id: int) -> list[dict]:
        """获取笔记库的所有簇"""
        clusters = (
            db.query(ConceptCluster)
            .filter_by(notebook_id=notebook_id)
            .filter(ConceptCluster.note_count > 0)
            .order_by(ConceptCluster.note_count.desc())
            .all()
        )
        return [c.to_dict() for c in clusters]

    def get_cluster_detail(self, db: Session, cluster_id: int) -> dict | None:
        """获取单个簇的详情（含笔记列表）"""
        cluster = db.query(ConceptCluster).filter_by(id=cluster_id).first()
        if not cluster:
            return None

        result = cluster.to_dict()

        # 查询簇内笔记
        cluster_notes = (
            db.query(ClusterNote).filter_by(cluster_id=cluster_id).all()
        )
        note_ids = [cn.note_id for cn in cluster_notes]
        if note_ids:
            notes = db.query(Note).filter(Note.id.in_(note_ids)).all()
            note_map = {n.id: n for n in notes}
            result["notes"] = [
                {
                    "id": nid,
                    "title": note_map[nid].title if nid in note_map else "(已删除)",
                }
                for nid in note_ids
            ]
        else:
            result["notes"] = []

        return result

    # ─── 辅助：更新簇中心向量 ───────────────────────

    def _update_cluster_center(
        self, db: Session, cluster: ConceptCluster, embeddings: dict[int, list[float]]
    ) -> None:
        """重新计算簇的中心向量（所有成员向量的均值）"""
        members = db.query(ClusterNote).filter_by(cluster_id=cluster.id).all()
        vecs = [embeddings.get(m.note_id) for m in members]
        vecs = [v for v in vecs if v is not None]
        if vecs:
            center = np.mean(vecs, axis=0).tolist()
            cluster.set_embedding(center)


# 全局单例
cluster_service = ClusterService()
