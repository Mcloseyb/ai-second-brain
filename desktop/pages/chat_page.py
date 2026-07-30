"""
知识问答页面
-----------
简洁聊天界面，SSE 流式显示 AI 回复。
"""

import json
import logging
import asyncio

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton,
    QLabel, QScrollArea,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QTextCursor

from services.api_client import api
from resources.styles.colors import Colors, Spacing, Radius, FontSize

logger = logging.getLogger(__name__)


class ChatPage(QWidget):
    """知识问答页面"""

    def __init__(self):
        super().__init__()
        self._conversation_id: int | None = None
        self._generating = False

        # ---- 布局 ----
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 页面标题栏
        header = QWidget()
        header.setFixedHeight(52)
        header.setStyleSheet(f"""
            background: {Colors.bg_content};
            border-bottom: 1px solid {Colors.border_default};
        """)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(Spacing.lg, Spacing.md, Spacing.lg, Spacing.md)

        title = QLabel("Chat")
        title.setStyleSheet(f"""
            color: {Colors.text_primary};
            font-size: {FontSize.xl}px;
            font-weight: 600;
            border: none;
        """)
        header_layout.addWidget(title)
        header_layout.addStretch()

        new_chat_btn = QPushButton("New Chat")
        new_chat_btn.setProperty("cssClass", "primary")
        new_chat_btn.setFixedHeight(32)
        new_chat_btn.clicked.connect(self._on_new_chat)
        header_layout.addWidget(new_chat_btn)

        layout.addWidget(header)

        # 对话显示区
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setStyleSheet(f"""
            QTextEdit {{
                background: {Colors.bg_content};
                color: {Colors.text_primary};
                border: none;
                padding: {Spacing.lg}px;
                font-size: {FontSize.lg}px;
                line-height: 1.6;
            }}
            QScrollBar:vertical {{
                background: transparent;
                width: 8px;
            }}
            QScrollBar::handle:vertical {{
                background: {Colors.border_light};
                border-radius: 4px;
                min-height: 30px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {Colors.border_focus};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0;
            }}
        """)
        layout.addWidget(self.chat_display)

        # 输入区
        input_container = QWidget()
        input_container.setStyleSheet(f"background: {Colors.bg_content};")
        input_layout = QHBoxLayout(input_container)
        input_layout.setContentsMargins(Spacing.lg, Spacing.md, Spacing.lg, Spacing.lg)

        self.input_box = QTextEdit()
        self.input_box.setPlaceholderText("Ask anything... (Enter to send, Shift+Enter for new line)")
        self.input_box.setMaximumHeight(120)
        self.input_box.setMinimumHeight(44)
        self.input_box.setStyleSheet(f"""
            QTextEdit {{
                background: {Colors.bg_input};
                color: {Colors.text_primary};
                border: 1px solid {Colors.border_default};
                border-radius: {Radius.lg}px;
                padding: 10px 14px;
                font-size: {FontSize.lg}px;
            }}
            QTextEdit:focus {{
                border-color: {Colors.border_focus};
                background: {Colors.bg_input_focus};
            }}
        """)
        input_layout.addWidget(self.input_box)

        self.send_btn = QPushButton("Send")
        self.send_btn.setProperty("cssClass", "primary")
        self.send_btn.setFixedSize(60, 44)
        self.send_btn.clicked.connect(self._on_send)
        input_layout.addWidget(self.send_btn)

        layout.addWidget(input_container)

        # 绑定 Enter 键
        self.input_box.installEventFilter(self)

        # 欢迎消息
        self._append_system_message(
            "Welcome to AI Second Brain.\n\n"
            "Ask me anything — I can help you research, write, and organize your knowledge."
        )

    # ============================================================
    # 事件处理
    # ============================================================

    def eventFilter(self, obj, event):
        from PySide6.QtCore import QEvent
        if obj == self.input_box and event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Return and not (
                event.modifiers() & Qt.KeyboardModifier.ShiftModifier
            ):
                self._on_send()
                return True
        return super().eventFilter(obj, event)

    def _on_send(self):
        if self._generating:
            return
        message = self.input_box.toPlainText().strip()
        if not message:
            return
        self.input_box.clear()
        self._append_user_message(message)
        self._generating = True
        self.send_btn.setEnabled(False)
        self.send_btn.setText("...")
        asyncio.ensure_future(self._send_message(message))

    def _on_new_chat(self):
        self._conversation_id = None
        self.chat_display.clear()
        self._append_system_message("New conversation started.")

    # ============================================================
    # SSE 流式发送
    # ============================================================

    async def _send_message(self, message: str):
        full_reply = ""
        self._append_assistant_prefix()

        try:
            async for line in api.stream_post("/api/chat", {
                "message": message,
                "conversation_id": self._conversation_id,
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
                if event_type == "token":
                    token = data.get("content", "")
                    full_reply += token
                    self._append_token(token)
                elif event_type == "done":
                    if self._conversation_id is None:
                        try:
                            result = await api.get("/api/conversations", params={"limit": 1})
                            convs = result.get("conversations", [])
                            if convs:
                                self._conversation_id = convs[0]["id"]
                        except Exception:
                            pass
                elif event_type == "error":
                    self._append_token(f"\n\nError: {data.get('content', 'Unknown error')}")
        except Exception as e:
            logger.error(f"Send failed: {e}")
            self._append_token(f"\n\nConnection failed: {e}")
        finally:
            self._generating = False
            self.send_btn.setEnabled(True)
            self.send_btn.setText("Send")

    # ============================================================
    # 显示辅助
    # ============================================================

    def _append_user_message(self, text: str):
        safe = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        self.chat_display.append(
            f'<div style="margin: 12px 0; padding: 10px 14px; '
            f'background: {Colors.chat_user_bg}; border-radius: {Radius.md}px;">'
            f'<span style="color: {Colors.accent_blue}; font-weight: 600;">You</span><br>'
            f'<span style="color: {Colors.text_primary};">{safe}</span></div>'
        )
        self._scroll_to_bottom()

    def _append_assistant_prefix(self):
        self.chat_display.append(
            f'<div style="margin: 12px 0; padding: 10px 14px; '
            f'background: {Colors.chat_assistant_bg}; border-radius: {Radius.md}px;">'
            f'<span style="color: {Colors.accent_green}; font-weight: 600;">Assistant</span><br>'
        )
        self._scroll_to_bottom()

    def _append_token(self, token: str):
        cursor = self.chat_display.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        safe = token.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        safe = safe.replace("\n", "<br>")
        cursor.insertHtml(safe)
        self._scroll_to_bottom()

    def _append_system_message(self, text: str):
        safe = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        safe = safe.replace("\n", "<br>")
        self.chat_display.append(
            f'<div style="margin: 12px 0; color: {Colors.text_tertiary}; '
            f'font-size: {FontSize.sm}px;">{safe}</div>'
        )
        self._scroll_to_bottom()

    def _scroll_to_bottom(self):
        sb = self.chat_display.verticalScrollBar()
        sb.setValue(sb.maximum())
