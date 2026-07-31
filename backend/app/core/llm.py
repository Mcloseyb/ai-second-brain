"""
LLM 调用统一封装
----------------
所有与大模型的交互必须通过此模块，不允许在业务代码中直接调用 OpenAI SDK。

功能:
  1. 普通对话（一次性返回）
  2. 流式对话（SSE 逐 token 返回）
  3. 自动重试（3次，指数退避）
  4. Token 估算与截断

使用方式:
    from app.core.llm import LLMService

    llm = LLMService()

    # 流式对话
    async for chunk in llm.chat_stream(messages=[...]):
        print(chunk, end="")

    # 普通对话
    reply = await llm.chat(messages=[...])
"""

import logging
import asyncio
from typing import AsyncGenerator

from openai import AsyncOpenAI

from app.config import settings

logger = logging.getLogger(__name__)


class LLMService:
    """LLM 服务封装，支持 DeepSeek API"""

    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
        )
        self.model = settings.default_model
        self.max_retries = 3
        self.retry_delay = 2  # 秒

    # ============================================================
    # 流式对话（核心方法 — SSE 推送）
    # ============================================================
    async def chat_stream(
        self,
        messages: list[dict[str, str]],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncGenerator[str, None]:
        """
        流式对话，逐 token 返回

        Args:
            messages: [{"role": "user", "content": "..."}, ...]
            temperature: 温度参数，默认使用配置值
            max_tokens: 最大生成 token 数

        Yields:
            str: 每次 yield 一个 token（或几个字符）
        """
        temp = temperature if temperature is not None else settings.temperature
        max_tok = max_tokens if max_tokens is not None else settings.max_tokens

        for attempt in range(1, self.max_retries + 1):
            try:
                stream = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temp,
                    max_tokens=max_tok,
                    stream=True,
                )

                async for chunk in stream:
                    delta = chunk.choices[0].delta
                    if delta.content:
                        yield delta.content

                return  # 成功，退出

            except Exception as e:
                logger.warning(
                    f"LLM 流式调用失败 (第 {attempt}/{self.max_retries} 次): {e}"
                )
                if attempt < self.max_retries:
                    await asyncio.sleep(self.retry_delay * attempt)
                else:
                    logger.error(f"LLM 流式调用最终失败: {e}")
                    yield f"\n\n[错误] AI 服务暂时不可用，请稍后重试: {e}"

    # ============================================================
    # 工具调用（Function Calling — Agent 专用）
    # ============================================================
    async def chat_with_tools(
        self,
        messages: list[dict[str, str]],
        tools: list[dict],
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ):
        """
        带工具调用的普通对话（DeepSeek OpenAI 兼容 Function Calling）

        Args:
            messages: 对话消息列表（system / user / assistant / tool）
            tools: OpenAI 工具定义列表
                    [{"type": "function", "function": {name, description, parameters}}]
            temperature: 工具调用用低温（默认 0，确定性决策）
            max_tokens: 最大生成 token 数

        Returns:
            message 对象 — 可能含 .content（最终回答）或 .tool_calls（工具调用）

        Raises:
            Exception: 重试 3 次仍失败时抛出，由 Agent 上层决定降级策略
        """
        max_tok = max_tokens if max_tokens is not None else settings.max_tokens

        for attempt in range(1, self.max_retries + 1):
            try:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=tools,
                    temperature=temperature,
                    max_tokens=max_tok,
                    stream=False,
                )
                return response.choices[0].message

            except Exception as e:
                logger.warning(
                    f"LLM 工具调用失败 (第 {attempt}/{self.max_retries} 次): {e}"
                )
                if attempt < self.max_retries:
                    await asyncio.sleep(self.retry_delay * attempt)
                else:
                    logger.error(f"LLM 工具调用最终失败: {e}")
                    raise  # 交由 Agent 上层降级处理

    # ============================================================
    # 普通对话（非流式 — 用于工具调用、Agent 内部通信等）
    # ============================================================
    async def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """
        普通对话，返回完整回复

        Args:
            messages: 对话消息列表
            temperature: 温度
            max_tokens: 最大 token

        Returns:
            str: AI 的完整回复
        """
        temp = temperature if temperature is not None else settings.temperature
        max_tok = max_tokens if max_tokens is not None else settings.max_tokens

        for attempt in range(1, self.max_retries + 1):
            try:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temp,
                    max_tokens=max_tok,
                    stream=False,
                )
                return response.choices[0].message.content or ""

            except Exception as e:
                logger.warning(
                    f"LLM 调用失败 (第 {attempt}/{self.max_retries} 次): {e}"
                )
                if attempt < self.max_retries:
                    await asyncio.sleep(self.retry_delay * attempt)
                else:
                    logger.error(f"LLM 调用最终失败: {e}")
                    return f"[错误] AI 服务暂时不可用，请稍后重试: {e}"


# 全局单例
llm_service = LLMService()
