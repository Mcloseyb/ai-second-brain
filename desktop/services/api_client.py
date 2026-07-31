"""
API 客户端封装
--------------
使用 httpx.AsyncClient 调用后端 FastAPI。
所有网络请求必须通过此模块，便于统一错误处理。

面试要点：
  为什么用 httpx 而不是 requests？
  → requests 是同步的，会阻塞 PySide6 的主线程，导致 UI 卡顿。
  → httpx 支持 async/await，配合 qasync 可以不阻塞 UI。
"""

import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# 后端地址
BASE_URL = "http://127.0.0.1:8000"


class APIClient:
    """异步 HTTP API 客户端"""

    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url.rstrip("/")
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """懒加载获取或创建 httpx 客户端"""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(60.0),  # AI 调用可能较慢
            )
        return self._client

    async def close(self):
        """关闭客户端"""
        if self._client:
            await self._client.aclose()
            self._client = None

    # ---- 通用请求方法 ----

    async def get(self, path: str, params: dict | None = None) -> dict:
        """GET 请求"""
        client = await self._get_client()
        try:
            resp = await client.get(path, params=params)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as e:
            logger.error(f"GET {path} 失败: {e}")
            raise

    async def post(self, path: str, data: dict | None = None) -> dict:
        """POST 请求（非流式）"""
        client = await self._get_client()
        try:
            resp = await client.post(path, json=data)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as e:
            logger.error(f"POST {path} 失败: {e}")
            raise

    async def put(self, path: str, data: dict) -> dict:
        """PUT 请求"""
        client = await self._get_client()
        try:
            resp = await client.put(path, json=data)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as e:
            logger.error(f"PUT {path} 失败: {e}")
            raise

    async def delete(self, path: str) -> dict:
        """DELETE 请求"""
        client = await self._get_client()
        try:
            resp = await client.delete(path)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as e:
            logger.error(f"DELETE {path} 失败: {e}")
            raise

    async def upload(self, path: str, file_path: str, fields: dict | None = None) -> dict:
        """
        文件上传（multipart/form-data）

        用法:
            result = await api.upload("/api/documents/import", "D:/notes/test.md", {"folder": "AI", "tags": "AI,LLM"})
        """
        import os
        client = await self._get_client()
        try:
            with open(file_path, "rb") as f:
                files = {"file": (os.path.basename(file_path), f)}
                data = fields or {}
                resp = await client.post(path, data=data, files=files)
                resp.raise_for_status()
                return resp.json()
        except httpx.HTTPError as e:
            logger.error(f"Upload {path} 失败: {e}")
            raise

    # ---- 流式请求 (SSE) ----

    async def stream_post(
        self, path: str, data: dict
    ):
        """
        SSE 流式 POST 请求
        返回一个异步迭代器，逐行 yield SSE 事件

        用法:
            async for line in api.stream_post("/api/chat", {"message": "hi"}):
                # line 是 "data: {...}" 格式
                process(line)
        """
        client = await self._get_client()
        try:
            async with client.stream("POST", path, json=data) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line:
                        yield line
        except httpx.HTTPError as e:
            logger.error(f"SSE POST {path} 失败: {e}")
            raise


# 全局单例
api = APIClient()
