"""
对话记忆管理
-----------
管理对话的短期记忆（上下文窗口）。

策略:
  - 滑动窗口: 保留最近 N 轮对话（默认 10 轮 = 20 条消息）
  - Token 感知: 估算总 token 数，超限时自动裁剪最早的对话
  - 持久化: 对话历史存 SQLite，这里只管理上下文窗口内的消息

使用方式:
    from app.core.memory import ConversationMemory

    memory = ConversationMemory(max_turns=10)
    memory.add_user_message("你好")
    memory.add_assistant_message("你好！有什么可以帮助你的？")
    messages = memory.get_messages()  # 可直接喂给 LLM
"""

import tiktoken
from typing import Optional


class ConversationMemory:
    """
    滑动窗口记忆管理器

    设计要点（面试可讲）:
      1. 为什么滑动窗口而不是全量记忆？
         → LLM 上下文窗口有限（DeepSeek 是 128K tokens），
           但放越多内容越快达到上限，且较早的对话通常不再相关。
      2. 为什么用 token 而不是字符数？
         → LLM 按 token 计费和限制，用 token 更精确。
      3. 未来可扩展为 "摘要记忆"（Summary Memory）：
         → 对早期对话生成摘要，保留信息而不占满窗口。
    """

    def __init__(
        self,
        max_turns: int = 10,
        max_tokens: int = 8000,
    ):
        """
        Args:
            max_turns: 最多保留的对话轮数（一轮 = 用户 + 助手）
            max_tokens: 记忆的最大 token 数（超过则裁剪）
        """
        self.max_turns = max_turns
        self.max_tokens = max_tokens
        self._messages: list[dict[str, str]] = []
        self._encoding = tiktoken.get_encoding("cl100k_base")  # DeepSeek 兼容

    def add_user_message(self, content: str) -> None:
        """添加用户消息"""
        self._messages.append({"role": "user", "content": content})
        self._trim()

    def add_assistant_message(self, content: str) -> None:
        """添加助手消息"""
        self._messages.append({"role": "assistant", "content": content})
        self._trim()

    def add_system_message(self, content: str) -> None:
        """设置系统消息（会替换已有的）"""
        # 移除已有的 system 消息
        self._messages = [m for m in self._messages if m["role"] != "system"]
        # 插入到最前面
        self._messages.insert(0, {"role": "system", "content": content})

    def get_messages(self) -> list[dict[str, str]]:
        """获取当前记忆中的所有消息（可直接传给 LLM）"""
        return list(self._messages)

    def get_last_n_messages(self, n: int) -> list[dict[str, str]]:
        """获取最近 n 条消息"""
        return self._messages[-n:]

    def clear(self) -> None:
        """清空记忆"""
        self._messages = []

    def total_tokens(self) -> int:
        """估算当前记忆的 token 总数"""
        text = "".join(m["content"] or "" for m in self._messages)
        return len(self._encoding.encode(text))

    def _trim(self) -> None:
        """裁剪记忆：先按轮数限制，再按 token 限制"""
        # 1. 按轮数限制（保留 system prompt）
        system_msgs = [m for m in self._messages if m["role"] == "system"]
        other_msgs = [m for m in self._messages if m["role"] != "system"]

        max_msg_count = self.max_turns * 2  # 一轮 = 2 条
        if len(other_msgs) > max_msg_count:
            other_msgs = other_msgs[-max_msg_count:]

        self._messages = system_msgs + other_msgs

        # 2. 按 token 限制
        while self.total_tokens() > self.max_tokens and len(other_msgs) > 2:
            # 保留 system + 最近的消息
            other_msgs = other_msgs[2:]  # 移除最早的一轮（user + assistant）
            self._messages = system_msgs + other_msgs

    def __repr__(self) -> str:
        return f"<ConversationMemory turns={len(self._messages)//2} tokens={self.total_tokens()}>"
