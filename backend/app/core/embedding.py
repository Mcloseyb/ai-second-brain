"""
Embedding 服务封装
----------------
使用 SiliconFlow API（OpenAI 兼容接口）调用 BAAI/bge-large-zh-v1.5 模型，
将文本转换为向量表示，供 ChromaDB 语义检索使用。

功能:
  1. 单条文本向量化
  2. 批量文本向量化（自动分批，节约 API 调用）
  3. 自动重试（3次，指数退避）

使用方式:
    from app.core.embedding import EmbeddingService

    emb = EmbeddingService()

    # 单条向量化
    vec = await emb.embed("Transformer 是一种基于自注意力机制的神经网络架构")

    # 批量向量化
    vecs = await emb.embed_batch(["文本1", "文本2", "文本3"])
"""

import logging
import asyncio
from typing import overload

from openai import AsyncOpenAI

from app.config import settings

logger = logging.getLogger(__name__)

# BGE 模型输出维度
BGE_LARGE_ZH_DIM = 1024
# 批量请求最大条数（SiliconFlow 限制）
MAX_BATCH_SIZE = 100


class EmbeddingService:
    """Embedding 服务封装 — SiliconFlow BAAI/bge-large-zh-v1.5"""

    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=settings.siliconflow_api_key,
            base_url=settings.siliconflow_base_url,
        )
        self.model = settings.embedding_model
        self.dim = BGE_LARGE_ZH_DIM
        self.max_retries = 3
        self.retry_delay = 2  # 秒

    # ============================================================
    # 单条文本向量化
    # ============================================================
    async def embed(self, text: str) -> list[float]:
        """
        将单条文本转换为向量

        Args:
            text: 输入文本

        Returns:
            list[float]: 向量（1024 维）
        """
        result = await self.embed_batch([text])
        return result[0]

    # ============================================================
    # 批量文本向量化
    # ============================================================
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        批量将文本转换为向量，自动分批处理

        Args:
            texts: 文本列表

        Returns:
            list[list[float]]: 向量列表，与输入顺序一致
        """
        if not texts:
            return []

        all_embeddings: list[list[float]] = []

        # 分批处理，避免单次请求过大
        for i in range(0, len(texts), MAX_BATCH_SIZE):
            batch = texts[i : i + MAX_BATCH_SIZE]

            for attempt in range(1, self.max_retries + 1):
                try:
                    response = await self.client.embeddings.create(
                        model=self.model,
                        input=batch,
                    )

                    # 按 index 排序后提取向量
                    sorted_data = sorted(response.data, key=lambda x: x.index)
                    batch_embeddings = [d.embedding for d in sorted_data]
                    all_embeddings.extend(batch_embeddings)
                    break  # 成功，跳出重试循环

                except Exception as e:
                    logger.warning(
                        f"Embedding 调用失败 (第 {attempt}/{self.max_retries} 次): {e}"
                    )
                    if attempt < self.max_retries:
                        await asyncio.sleep(self.retry_delay * attempt)
                    else:
                        logger.error(f"Embedding 调用最终失败: {e}")
                        # 失败的 batch 返回零向量占位
                        all_embeddings.extend(
                            [[0.0] * self.dim] * len(batch)
                        )

        return all_embeddings

    # ============================================================
    # 便捷方法：计算两条文本的余弦相似度
    # ============================================================
    async def similarity(self, text1: str, text2: str) -> float:
        """
        计算两条文本的语义相似度（余弦相似度）

        Args:
            text1: 文本1
            text2: 文本2

        Returns:
            float: 相似度 [0, 1]
        """
        vecs = await self.embed_batch([text1, text2])
        return self._cosine_similarity(vecs[0], vecs[1])

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        """计算两个向量的余弦相似度"""
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)


# 全局单例
embedding_service = EmbeddingService()
