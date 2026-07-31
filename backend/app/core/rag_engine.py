"""
RAG 引擎 — 笔记向量化 + ChromaDB 存储 + 语义检索
----------------------------------------------
将笔记内容向量化存入 ChromaDB，支持语义搜索。
设计原则:
  - 一篇笔记 = 一个 ChromaDB 文档（笔记通常较短，暂不分块）
  - 嵌入文本 = "{title}\n\n{content}"，标题前置以增强语义权重
  - 使用余弦距离（cosine），相似度 = 1 - distance

使用方式:
    from app.core.rag_engine import rag_engine

    # 索引笔记
    await rag_engine.index_note(note_id=1, title="...", content="...")

    # 语义搜索
    results = await rag_engine.search("关于 Transformer 的笔记")

    # 删除笔记
    await rag_engine.remove_note(note_id=1)
"""

import logging
from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.config import settings
from app.core.embedding import embedding_service

logger = logging.getLogger(__name__)

# ChromaDB collection 名称
NOTES_COLLECTION = "notes"
# 默认返回结果数
DEFAULT_TOP_K = 5


class RAGEngine:
    """RAG 引擎 — 管理笔记向量存储与语义检索"""

    def __init__(self):
        self._client: chromadb.PersistentClient | None = None
        self._collection: chromadb.Collection | None = None

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

    # ============================================================
    # 语义搜索
    # ============================================================
    async def search(
        self,
        query: str,
        top_k: int = DEFAULT_TOP_K,
        threshold: float = 0.0,
    ) -> list[dict[str, Any]]:
        """
        语义搜索笔记 — 返回最相关的 Top-K 条笔记

        Args:
            query: 搜索查询（自然语言）
            top_k: 返回结果数
            threshold: 相似度阈值 [0, 1]，低于此值的结果会被过滤

        Returns:
            [{note_id, title, text, similarity}, ...]  按相似度降序排列
        """
        if not query.strip():
            return []

        # 生成查询向量
        query_vec = await embedding_service.embed(query)

        # ChromaDB 检索
        n_results = min(top_k, self.collection.count())
        if n_results == 0:
            return []

        results = self.collection.query(
            query_embeddings=[query_vec],
            n_results=n_results,
            include=["metadatas", "documents", "distances"],
        )

        # 格式化结果
        items = []
        if results["ids"] and results["ids"][0]:
            for i, doc_id in enumerate(results["ids"][0]):
                distance = results["distances"][0][i] if results["distances"] else 0.0
                # 余弦距离 → 相似度: similarity = 1 - distance
                similarity = round(1.0 - distance, 4)
                metadata = results["metadatas"][0][i] if results["metadatas"] else {}
                text = results["documents"][0][i] if results["documents"] else ""

                if similarity >= threshold:
                    items.append({
                        "note_id": metadata.get("note_id", int(doc_id)),
                        "title": metadata.get("title", ""),
                        "text": text,
                        "similarity": similarity,
                    })

        return items

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
