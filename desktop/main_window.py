"""
主窗口
------
QTabWidget 包含 4 个页面:
  1. 智能笔记 (NotesPage)    — P2 实现
  2. 知识问答 (ChatPage)     — P1 实现
  3. 深度研究 (ResearchPage)  — P5 实现
  4. 个人看板 (DashboardPage) — P7 实现

布局:
┌─────────────────────────────────────────────┐
│  🧠 AI Second Brain              ─ □ ×      │
├─────────────────────────────────────────────┤
│  [📝 智能笔记] [💬 知识问答] [🔬 深度研究] [📊 看板] │
├─────────────────────────────────────────────┤
│                                               │
│              当前页面的内容区域                  │
│                                               │
├─────────────────────────────────────────────┤
│  🟢 后端运行中  |  DeepSeek API 已连接       │
└─────────────────────────────────────────────┘
"""

import logging

from PySide6.QtWidgets import (
    QMainWindow, QTabWidget, QStatusBar, QLabel, QWidget, QVBoxLayout,
)
from PySide6.QtCore import Qt, QTimer

from pages.chat_page import ChatPage

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """主窗口"""

    def __init__(self):
        super().__init__()

        self.setWindowTitle("🧠 AI Second Brain — AI 协同个人知识库管理系统")
        self.resize(1100, 750)

        # ---- 中心区域: Tab 页 ----
        self.tab_widget = QTabWidget()
        self.setCentralWidget(self.tab_widget)

        # 创建各页面
        self.chat_page = ChatPage()
        self.notes_placeholder = self._create_placeholder("📝 智能笔记", "P2 阶段实现")
        self.research_placeholder = self._create_placeholder("🔬 深度研究", "P5 阶段实现")
        self.dashboard_placeholder = self._create_placeholder("📊 个人看板", "P7 阶段实现")

        # 添加到 Tab
        self.tab_widget.addTab(self.notes_placeholder, "📝 智能笔记")
        self.tab_widget.addTab(self.chat_page, "💬 知识问答")
        self.tab_widget.addTab(self.research_placeholder, "🔬 深度研究")
        self.tab_widget.addTab(self.dashboard_placeholder, "📊 看板")

        # 默认打开知识问答（P1 已完成的功能）
        self.tab_widget.setCurrentIndex(1)

        # ---- 底部状态栏 ----
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        self.status_backend = QLabel("🟢 后端已连接")
        self.status_api = QLabel("🤖 DeepSeek API")
        self.status_bar.addWidget(self.status_backend)
        self.status_bar.addPermanentWidget(self.status_api)

        # 健康检查
        self._check_health()

    def _create_placeholder(self, title: str, description: str) -> QWidget:
        """创建一个占位页面（功能未实现时显示）"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        label = QLabel(f"<h1>{title}</h1><p>{description}</p>")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)

        return widget

    def _check_health(self):
        """检查后端健康状态并更新状态栏"""
        async def check():
            try:
                from services.api_client import api
                result = await api.get("/health")
                if result.get("status") == "ok":
                    self.status_backend.setText("🟢 后端已连接")
                else:
                    self.status_backend.setText("🟡 后端异常")
            except Exception:
                self.status_backend.setText("🔴 后端未连接")

        # 用 QTimer 延迟执行异步检查
        import asyncio
        QTimer.singleShot(1000, lambda: asyncio.ensure_future(check()))
