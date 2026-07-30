"""
SSE 流式客户端
-------------
解析 Server-Sent Events 协议，提取事件数据。

SSE 协议格式:
  data: {"type": "token", "content": "你"}\n\n
  data: {"type": "token", "content": "好"}\n\n
  data: {"type": "done", ...}\n\n

事件类型:
  - thinking: AI 正在思考
  - token: 文本 token（逐字流式输出）
  - done: 对话完成
  - error: 发生错误
"""

import json
import logging
from typing import AsyncGenerator
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class SSEEvent:
    """一个 SSE 事件"""
    type: str
    content: str = ""
    message_id: int = 0
    tokens: int = 0
    raw: dict = field(default_factory=dict)


class SSEClient:
    """
    SSE 客户端 — 解析流式事件

    面试可讲: SSE 如何工作？
      1. 客户端发起 HTTP POST 请求
      2. 服务器返回 Content-Type: text/event-stream
      3. 服务器持续推送 "data: {json}\n\n" 格式的事件
      4. 客户端逐行读取，解析 JSON
      5. 连接关闭表示流结束
    """

    @staticmethod
    async def parse_stream(lines: AsyncGenerator[str, None]) -> AsyncGenerator[SSEEvent, None]:
        """
        解析 SSE 事件流

        Args:
            lines: 异步行迭代器

        Yields:
            SSEEvent: 解析后的事件
        """
        async for line in lines:
            line = line.strip()

            # 跳过空行和注释
            if not line or line.startswith(":"):
                continue

            # 解析 "data: {...}" 行
            if line.startswith("data:"):
                data_str = line[5:].strip()
                if not data_str:
                    continue

                try:
                    data = json.loads(data_str)
                    event = SSEEvent(
                        type=data.get("type", "unknown"),
                        content=data.get("content", ""),
                        message_id=data.get("message_id", 0),
                        tokens=data.get("tokens", 0),
                        raw=data,
                    )
                    yield event
                except json.JSONDecodeError as e:
                    logger.warning(f"SSE JSON 解析失败: {data_str[:100]}... error={e}")

    @staticmethod
    def format_event(event: SSEEvent) -> str:
        """将事件格式化为可显示的文本"""
        if event.type == "thinking":
            return f"🤔 {event.content}"
        elif event.type == "token":
            return event.content
        elif event.type == "done":
            return ""  # 不显示
        elif event.type == "error":
            return f"\n❌ 错误: {event.content}"
        else:
            return event.content
