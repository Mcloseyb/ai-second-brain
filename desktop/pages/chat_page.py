"""
知识问答页面（P1 核心功能）
--------------------------
用户输入问题 → 显示 AI 流式回复。

界面布局:
┌──────────────────────────────────────────────────┐
│  [对话历史区 — QScrollArea]                        │
│                                                    │
│  👤 你: 你好                                       │
│  🤖 AI: 你好！有什么可以帮助你的？                  │
│  👤 你: 什么是AI Agent？                            │
│  🤖 AI: AI Agent 是指...                           │
│                                                    │
├──────────────────────────────────────────────────┤
│  [输入框                        ] [发送] [新对话]  │
└──────────────────────────────────────────────────┘

技术细节（面试可讲）:
  1. SSE 流式: 不是一次等完再显示，而是来一个 token 显示一个
  2. qasync: Qt 是同步事件循环，qasync 桥接到 asyncio
  3. QTextEdit.append() 每次追加一个 token，用 QScrollBar 自动滚到底部
"""

import json
import logging
import asyncio
from datetime import datetime

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton,
    QScrollArea, QLabel, QSplitter,
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont, QColor, QTextCursor

from services.api_client import api

logger = logging.getLogger(__name__)


class ChatPage(QWidget):
    """知识问答页面"""

    # 信号: AI 回复完成后触发
    reply_finished = Signal(str)

    def __init__(self):
        super().__init__()

        # 当前对话 ID
        self.current_conversation_id: int | None = None
        # 是否正在生成回复
        self._generating = False

        # ---- 布局 ----
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)

        # 对话显示区
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setFont(QFont("Microsoft YaHei", 10))
        self.chat_display.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e2e;
                color: #cdd6f4;
                border: 1px solid #313244;
                border-radius: 8px;
                padding: 12px;
            }
        """)
        main_layout.addWidget(self.chat_display)

        # 输入区
        input_layout = QHBoxLayout()

        self.input_box = QTextEdit()
        self.input_box.setPlaceholderText("输入你的问题... (Enter 发送, Shift+Enter 换行)")
        self.input_box.setMaximumHeight(100)
        self.input_box.setFont(QFont("Microsoft YaHei", 10))
        self.input_box.setStyleSheet("""
            QTextEdit {
                background-color: #313244;
                color: #cdd6f4;
                border: 1px solid #45475a;
                border-radius: 8px;
                padding: 8px;
            }
        """)
        input_layout.addWidget(self.input_box)

        self.send_btn = QPushButton("发送")
        self.send_btn.setFixedWidth(80)
        self.send_btn.setFixedHeight(80)
        self.send_btn.setStyleSheet("""
            QPushButton {
                background-color: #89b4fa;
                color: #1e1e2e;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #74c7ec;
            }
            QPushButton:disabled {
                background-color: #45475a;
                color: #6c7086;
            }
        """)
        self.send_btn.clicked.connect(self._on_send)
        input_layout.addWidget(self.send_btn)

        self.new_chat_btn = QPushButton("新对话")
        self.new_chat_btn.setFixedWidth(80)
        self.new_chat_btn.setFixedHeight(80)
        self.new_chat_btn.setStyleSheet("""
            QPushButton {
                background-color: #a6e3a1;
                color: #1e1e2e;
                border: none;
                border-radius: 8px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #94e2d5;
            }
        """)
        self.new_chat_btn.clicked.connect(self._on_new_chat)
        input_layout.addWidget(self.new_chat_btn)

        main_layout.addLayout(input_layout)

        # 绑定 Enter 键发送
        self.input_box.installEventFilter(self)

        # 欢迎消息
        self._append_system_message(
            "👋 欢迎使用 AI Second Brain！\n\n"
            "我是你的 AI 知识助手，现在可以和我对话了。\n"
            "P1 阶段 — 基础流式对话已就绪。"
        )

    # ============================================================
    # 事件处理
    # ============================================================

    def eventFilter(self, obj, event):
        """拦截 Enter 键发送消息"""
        from PySide6.QtCore import QEvent
        from PySide6.QtGui import QKeyEvent

        if obj == self.input_box and event.type() == QEvent.Type.KeyPress:
            key_event = event
            # Enter 发送（不带 Shift）
            if key_event.key() == Qt.Key.Key_Return and not (
                key_event.modifiers() & Qt.KeyboardModifier.ShiftModifier
            ):
                self._on_send()
                return True
        return super().eventFilter(obj, event)

    def _on_send(self):
        """发送按钮点击处理"""
        if self._generating:
            return

        message = self.input_box.toPlainText().strip()
        if not message:
            return

        # 清空输入框
        self.input_box.clear()

        # 显示用户消息
        self._append_user_message(message)

        # 禁用发送按钮
        self._generating = True
        self.send_btn.setEnabled(False)
        self.send_btn.setText("思考中...")

        # 异步发送
        asyncio.ensure_future(self._send_message(message))

    def _on_new_chat(self):
        """新建对话"""
        self.current_conversation_id = None
        self.chat_display.clear()
        self._append_system_message("🆕 新对话已开始")

    # ============================================================
    # SSE 流式发送
    # ============================================================

    async def _send_message(self, message: str):
        """发送消息并处理 SSE 流式回复"""
        # 开始显示 AI 回复
        self._append_assistant_prefix()

        full_reply = ""

        try:
            async for line in api.stream_post("/api/chat", {
                "message": message,
                "conversation_id": self.current_conversation_id,
            }):
                if not line.startswith("data:"):
                    continue

                data_str = line[5:].strip()
                if not data_str:
                    continue

                try:
                    data = json.loads(data_str)
                except json.JSONDecodeError:
                    continue

                event_type = data.get("type")

                if event_type == "thinking":
                    pass  # 跳过思考状态

                elif event_type == "token":
                    token = data.get("content", "")
                    full_reply += token
                    self._append_token(token)

                elif event_type == "done":
                    # 保存对话 ID
                    msg_id = data.get("message_id")
                    if msg_id:
                        # 从后端获取对话 ID
                        pass

                elif event_type == "error":
                    self._append_token(f"\n\n❌ 错误: {data.get('content', '未知错误')}")

        except Exception as e:
            logger.error(f"发送消息失败: {e}")
            self._append_token(f"\n\n❌ 连接失败: {e}")

        finally:
            # 恢复发送按钮
            self._generating = False
            self.send_btn.setEnabled(True)
            self.send_btn.setText("发送")

            # 保存对话 ID（从第一次对话获取）
            if self.current_conversation_id is None and full_reply:
                # 从对话列表里获取最新的
                try:
                    result = await api.get("/api/conversations", params={"limit": 1})
                    convs = result.get("conversations", [])
                    if convs:
                        self.current_conversation_id = convs[0]["id"]
                except Exception:
                    pass

            self.reply_finished.emit(full_reply)

    # ============================================================
    # 显示辅助方法
    # ============================================================

    def _append_user_message(self, text: str):
        """显示用户消息"""
        time_str = datetime.now().strftime("%H:%M")
        self.chat_display.append(
            f'<div style="margin: 8px 0;">'
            f'<span style="color: #89b4fa; font-weight: bold;">👤 你</span>'
            f'<span style="color: #6c7086; font-size: 0.8em;"> {time_str}</span><br>'
            f'<span style="color: #cdd6f4;">{text}</span>'
            f'</div>'
        )
        self._scroll_to_bottom()

    def _append_assistant_prefix(self):
        """显示 AI 回复前缀"""
        time_str = datetime.now().strftime("%H:%M")
        self.chat_display.append(
            f'<div style="margin: 8px 0;">'
            f'<span style="color: #a6e3a1; font-weight: bold;">🤖 AI</span>'
            f'<span style="color: #6c7086; font-size: 0.8em;"> {time_str}</span><br>'
        )
        self._scroll_to_bottom()

    def _append_token(self, token: str):
        """追加一个 token 到当前 AI 回复（流式显示核心）"""
        # 获取当前光标
        cursor = self.chat_display.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        # HTML 转义
        safe_token = token.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        # 换行转 <br>
        safe_token = safe_token.replace("\n", "<br>")

        cursor.insertHtml(safe_token)
        self._scroll_to_bottom()

    def _append_system_message(self, text: str):
        """显示系统消息"""
        self.chat_display.append(
            f'<div style="margin: 8px 0; color: #6c7086; font-style: italic;">'
            f'{text}</div>'
        )
        self._scroll_to_bottom()

    def _scroll_to_bottom(self):
        """滚动到底部"""
        scrollbar = self.chat_display.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
