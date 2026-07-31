"""
RAG 引擎 — 笔记向量化 + ChromaDB 存储 + 混合检索
----------------------------------------------
将笔记内容向量化存入 ChromaDB，支持语义搜索 + BM25 关键词检索。
设计原则:
  - 一篇笔记 = 一个 ChromaDB 文档（笔记通常较短，暂不分块）
  - 嵌入文本 = "{title}\n\n{content}"，标题前置以增强语义权重
  - 使用余弦距离（cosine），相似度 = 1 - distance
  - 混合检索: 语义 0.7 + BM25 关键词 0.3，自动融合排序

使用方式:
    from app.core.rag_engine import rag_engine

    # 索引笔记
    await rag_engine.index_note(note_id=1, title="...", content="...")

    # 混合搜索（默认）
    results = await rag_engine.search("关于 Transformer 的笔记")

    # 纯语义搜索
    results = await rag_engine.search("query", hybrid=False)

    # 删除笔记
    await rag_engine.remove_note(note_id=1)
"""

import logging
from pathlib import Path
from typing import Any

import chromadb
import jieba
from chromadb.config import Settings as ChromaSettings
from rank_bm25 import BM25Okapi

from app.config import settings
from app.core.embedding import embedding_service

logger = logging.getLogger(__name__)

# ChromaDB collection 名称
NOTES_COLLECTION = "notes"
# 默认返回结果数
DEFAULT_TOP_K = 5
# 混合检索权重
SEMANTIC_WEIGHT = 0.7
BM25_WEIGHT = 0.3


def _tokenize(text: str) -> list[str]:
    """
    中文+英文混合分词
    - 中文用 jieba 分词
    - 英文/数字按空白分割
    """
    # jieba.cut 返回生成器，转为 list
    tokens = list(jieba.cut(text))
    # 过滤掉纯空白/标点 token
    result: list[str] = []
    for t in tokens:
        t = t.strip()
        if t and t not in (" ", "\n", "\t", "，", "。", "、", "；", "：", "？", "！", "…"):
            # 英文词组按空格再拆一次
            result.extend(t.split())
    return result


class RAGEngine:
    """RAG 引擎 — 管理笔记向量存储与混合检索"""

    def __init__(self):
        self._client: chromadb.PersistentClient | None = None
        self._collection: chromadb.Collection | None = None
        # BM25 索引缓存
        self._bm25: BM25Okapi | None = None
        self._bm25_note_ids: list[int] = []        # 与 BM25 corpus 对应的 note_id
        self._bm25_titles: dict[int, str] = {}      # note_id → title（供搜索结果使用）
        self._bm25_texts: dict[int, str] = {}       # note_id → full text

    # ============================================================
    # 懒加载属性（首次使用时初始化 ChromaDB）
    # ============================================================
    @property
    def client(self) -> chromadb.PersistentClient:
        if self._client is None:
            chroma_path = settings.chroma_path
            chroma_path.mkdir(parents=True, exist_ok=True)
            self._client = chromadb.PersistentClient(
                path=str(chroma_path),
                settings=ChromaSettings(anonymized_telemetry=False),
            )
            logger.info(f"ChromaDB 客户端已初始化: {chroma_path}")
        return self._client

    @property
    def collection(self) -> chromadb.Collection:
        if self._collection is None:
            self._collection = self.client.get_or_create_collection(
                name=NOTES_COLLECTION,
                metadata={"hnsw:space": "cosine"},  # 余弦距离
            )
            logger.info(f"ChromaDB Collection 已就绪: {NOTES_COLLECTION}")
        return self._collection

    # ============================================================
    # BM25 索引管理
    # ============================================================
    def _invalidate_bm25(self) -> None:
        """标记 BM25 索引失效，下次搜索时重建"""
        self._bm25 = None
        self._bm25_note_ids = []

    def _ensure_bm25(self) -> None:
        """确保 BM25 索引已构建（懒加载）"""
        if self._bm25 is not None:
            return

        # 从 ChromaDB 获取所有笔记文本
        try:
            all_data = self.collection.get(
                include=["metadatas", "documents"],
            )
        except Exception as e:
            logger.warning(f"获取 ChromaDB 数据失败: {e}")
            self._bm25 = BM25Okapi([])
            return

        if not all_data or not all_data["ids"]:
            self._bm25 = BM25Okapi([])
            return

        corpus: list[list[str]] = []
        note_ids: list[int] = []
        titles: dict[int, str] = {}
        texts: dict[int, str] = {}

        for i, doc_id in enumerate(all_data["ids"]):
            metadata = all_data["metadatas"][i] if all_data["metadatas"] else {}
            document = all_data["documents"][i] if all_data["documents"] else ""
            note_id = metadata.get("note_id", int(doc_id))
            title = metadata.get("title", "")

            # 全文分词（用于 BM25 匹配）
            full_text = f"{title} {document}"
            tokens = _tokenize(full_text)
            if tokens:
                corpus.append(tokens)
                note_ids.append(note_id)
                titles[note_id] = title
                texts[note_id] = document

        self._bm25 = BM25Okapi(corpus) if corpus else BM25Okapi([])
        self._bm25_note_ids = note_ids
        self._bm25_titles = titles
        self._bm25_texts = texts
        logger.info(f"BM25 索引已构建: {len(note_ids)} 篇笔记")

    def _bm25_search(self, query: str, top_k: int = DEFAULT_TOP_K) -> list[dict[str, Any]]:
        """
        BM25 关键词检索

        Args:
            query: 搜索查询
            top_k: 返回结果数

        Returns:
            [{note_id, title, text, score}, ...] score 已归一化到 [0, 1]
        """
        self._ensure_bm25()

        if not self._bm25_note_ids or not self._bm25 or not self._bm25.corpus_size:
            return []

        query_tokens = _tokenize(query)
        if not query_tokens:
            return []

        # BM25 原始分数（无上界）
        raw_scores = self._bm25.get_scores(query_tokens)

        # 获取 top_k 的索引和分数
        n = min(top_k, len(raw_scores))
        # 取最大 top_k 个
        indexed = sorted(
            enumerate(raw_scores), key=lambda x: x[1], reverse=True
        )[:n]

        # 归一化：除以最大分数
        max_score = indexed[0][1] if indexed else 1.0
        results: list[dict[str, Any]] = []
        for idx, raw_score in indexed:
            norm_score = round(raw_score / max_score, 4) if max_score > 0 else 0.0
            note_id = self._bm25_note_ids[idx]
            results.append({
                "note_id": note_id,
                "title": self._bm25_titles.get(note_id, ""),
                "text": self._bm25_texts.get(note_id, ""),
                "score": norm_score,
            })

        return results

    # ============================================================
    # 笔记索引
    # ============================================================
    async def index_note(self, note_id: int, title: str, content: str) -> None:
        """
        将一篇笔记向量化并存入 ChromaDB（已存在则更新）

        Args:
            note_id: 笔记 ID
            title: 笔记标题
            content: 笔记正文（Markdown）
        """
        # 拼接标题和正文，标题前置以增强语义权重
        text = f"{title}\n\n{content}" if title else content

        # 跳过空笔记
        if not text.strip():
            logger.warning(f"笔记 {note_id} 内容为空，跳过索引")
            return

        # 生成向量
        embedding = await embedding_service.embed(text)

        # 写入 ChromaDB（upsert: 存在则更新）
        doc_id = str(note_id)
        self.collection.upsert(
            ids=[doc_id],
            embeddings=[embedding],
            metadatas=[{
                "note_id": note_id,
                "title": title[:200],  # 截断防止元数据过大
            }],
            documents=[text[:2000]],  # 存储前 2000 字符用于展示
        )
        logger.info(f"笔记 {note_id} 已索引: {title[:40]}")

        # BM25 索引失效
        self._invalidate_bm25()

    # ============================================================
    # 笔记删除
    # ============================================================
    async def remove_note(self, note_id: int) -> None:
        """
        从 ChromaDB 中删除一篇笔记的向量

        Args:
            note_id: 笔记 ID
        """
        doc_id = str(note_id)
        try:
            self.collection.delete(ids=[doc_id])
            logger.info(f"笔记 {note_id} 已从向量库删除")
        except Exception as e:
            logger.warning(f"删除笔记 {note_id} 向量失败（可能不存在）: {e}")

        # BM25 索引失效
        self._invalidate_bm25()

    # ============================================================
    # 混合搜索
    # ============================================================
    async def search(
        self,
        query: str,
        top_k: int = DEFAULT_TOP_K,
        threshold: float = 0.0,
        hybrid: bool = True,
    ) -> list[dict[str, Any]]:
        """
        混合搜索笔记 — 语义检索 + BM25 关键词检索

        Args:
            query: 搜索查询（自然语言）
            top_k: 返回结果数
            threshold: 相似度阈值 [0, 1]，低于此值的结果会被过滤
            hybrid: True=混合检索(semantic 0.7 + BM25 0.3), False=纯语义检索

        Returns:
            [{note_id, title, text, similarity}, ...]  按相似度降序排列
        """
        if not query.strip():
            return []

        # ---- 语义检索 ----
        query_vec = await embedding_service.embed(query)

        n_results = min(top_k * 2, max(self.collection.count(), 1))  # 多取一些供融合
        semantic_results: dict[int, dict] = {}

        try:
            chroma_results = self.collection.query(
                query_embeddings=[query_vec],
                n_results=n_results,
                include=["metadatas", "documents", "distances"],
            )

            if chroma_results["ids"] and chroma_results["ids"][0]:
                for i, doc_id in enumerate(chroma_results["ids"][0]):
                    distance = chroma_results["distances"][0][i] if chroma_results["distances"] else 0.0
                    similarity = round(1.0 - distance, 4)
                    metadata = chroma_results["metadatas"][0][i] if chroma_results["metadatas"] else {}
                    text = chroma_results["documents"][0][i] if chroma_results["documents"] else ""
                    note_id = metadata.get("note_id", int(doc_id))
                    semantic_results[note_id] = {
                        "note_id": note_id,
                        "title": metadata.get("title", ""),
                        "text": text,
                        "semantic_score": similarity,
                        "bm25_score": 0.0,
                    }
        except Exception as e:
            logger.error(f"语义检索失败: {e}")

        # ---- BM25 关键词检索 ----
        bm25_results: dict[int, float] = {}
        if hybrid:
            try:
                bm25_list = self._bm25_search(query, top_k=top_k * 2)
                for r in bm25_list:
                    bm25_results[r["note_id"]] = r["score"]
            except Exception as e:
                logger.error(f"BM25 检索失败: {e}")

        # ---- 融合 ----
        if hybrid and bm25_results:
            # 将 BM25 分数注入到语义结果中
            for note_id, score in bm25_results.items():
                if note_id in semantic_results:
                    semantic_results[note_id]["bm25_score"] = score
                else:
                    semantic_results[note_id] = {
                        "note_id": note_id,
                        "title": self._bm25_titles.get(note_id, ""),
                        "text": self._bm25_texts.get(note_id, ""),
                        "semantic_score": 0.0,
                        "bm25_score": score,
                    }

            # 加权融合: final = semantic_weight * semantic + bm25_weight * bm25
            for note_id, item in semantic_results.items():
                fused = (
                    SEMANTIC_WEIGHT * item["semantic_score"]
                    + BM25_WEIGHT * item["bm25_score"]
                )
                item["similarity"] = round(fused, 4)
        else:
            # 纯语义检索
            for item in semantic_results.values():
                item["similarity"] = item["semantic_score"]

        # ---- 排序 + 阈值过滤 + Top-K ----
        items = sorted(
            semantic_results.values(),
            key=lambda x: x["similarity"],
            reverse=True,
        )

        final: list[dict[str, Any]] = []
        for item in items:
            if item["similarity"] >= threshold:
                final.append({
                    "note_id": item["note_id"],
                    "title": item["title"],
                    "text": item["text"],
                    "similarity": item["similarity"],
                })
                if len(final) >= top_k:
                    break

        return final

    # ============================================================
    # 全量索引重建
    # ============================================================
    async def rebuild_index(self, notes: list) -> int:
        """
        清空向量库并全量重建索引（用于启动时或数据修复）

        Args:
            notes: Note ORM 对象列表（需有 id, title, content 属性）

        Returns:
            int: 已索引的笔记数量
        """
        # 清空现有 collection
        try:
            self.client.delete_collection(NOTES_COLLECTION)
            self._collection = None  # 触发重建
        except Exception:
            pass

        # 逐条索引
        count = 0
        for note in notes:
            try:
                await self.index_note(
                    note_id=note.id,
                    title=note.title,
                    content=note.content,
                )
                count += 1
            except Exception as e:
                logger.error(f"重建索引失败 — 笔记 {note.id}: {e}")

        logger.info(f"索引重建完成: {count}/{len(notes)} 篇笔记")
        return count

    # ============================================================
    # 工具方法
    # ============================================================
    def count(self) -> int:
        """返回已索引的笔记数量"""
        try:
            return self.collection.count()
        except Exception:
            return 0

    def is_indexed(self, note_id: int) -> bool:
        """检查某篇笔记是否已索引"""
        try:
            result = self.collection.get(ids=[str(note_id)])
            return bool(result and result["ids"])
        except Exception:
            return False


# 全局单例
rag_engine = RAGEngine()
