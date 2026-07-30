"""
主窗口 — Notion 风格布局
------------------------
┌───────────┬──────────────────────────────────────┐
│ Sidebar   │  Content Area (QStackedWidget)        │
│ (240px)   │                                       │
│           │  Pages:                               │
│ Workspace │  - Chat (P1 done)                     │
│ Switcher  │  - Notes (P2)                         │
│           │  - Graph (P1 done, sample data)       │
│ Search    │  - Dashboard (P7)                     │
│           │                                       │
│ NAV       │                                       │
│ - Chat    │                                       │
│ - Notes   │                                       │
│ - Graph   │                                       │
│ - Dash    │                                       │
│           │                                       │
│ User      │                                       │
│ Settings  │                                       │
└───────────┴──────────────────────────────────────┘
"""

import asyncio
import logging

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QStackedWidget,
    QStatusBar, QLabel,
)
from PySide6.QtCore import Qt, QTimer

from widgets.sidebar import Sidebar
from pages.chat_page import ChatPage
from pages.notes_page import NotesPage
from pages.graph_page import GraphPage
from resources.styles.colors import Colors, FontSize

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Notion 风格主窗口"""

    PAGE_IDS = ["chat", "notes", "graph", "dashboard"]

    def __init__(self):
        super().__init__()

        self.setWindowTitle("AI Second Brain")
        self.resize(1200, 780)
        self.setMinimumSize(900, 600)

        # ============================================================
        # 中心区域: 侧边栏 + 内容
        # ============================================================
        central = QWidget()
        self.setCentralWidget(central)

        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # 左侧边栏
        self.sidebar = Sidebar()
        self.sidebar.navigation_changed.connect(self._on_navigation)
        root_layout.addWidget(self.sidebar)

        # 右侧内容区
        self.content_stack = QStackedWidget()
        self.content_stack.setStyleSheet(f"background: {Colors.bg_content};")

        # 创建各页面
        self.chat_page = ChatPage()
        self.notes_page = NotesPage()
        self.graph_page = GraphPage()

        # 占位页面（dashboard）
        self.dashboard_page = self._create_placeholder("Dashboard", "Phase 7")

        # 按 PAGE_IDS 顺序添加（索引对齐）
        self.content_stack.addWidget(self.chat_page)       # index 0 — chat
        self.content_stack.addWidget(self.notes_page)       # index 1 — notes
        self.content_stack.addWidget(self.graph_page)       # index 2 — graph
        self.content_stack.addWidget(self.dashboard_page)   # index 3 — dashboard

        root_layout.addWidget(self.content_stack)

        # 默认显示 Chat
        self.content_stack.setCurrentIndex(0)

        # ============================================================
        # 状态栏
        # ============================================================
        status = QStatusBar()
        status.setStyleSheet(f"""
            QStatusBar {{
                background: #151514;
                color: {Colors.text_tertiary};
                border-top: 1px solid {Colors.border_default};
                font-size: {FontSize.xs}px;
                padding: 2px 12px;
            }}
        """)
        self.setStatusBar(status)

        self.status_label = QLabel("Ready")
        status.addWidget(self.status_label)

        status.addPermanentWidget(QLabel("DeepSeek API"))

        # 启动后检查后端健康
        QTimer.singleShot(1500, lambda: asyncio.ensure_future(self._check_health()))

    # ============================================================
    # 导航
    # ============================================================

    def _on_navigation(self, page_id: str):
        """侧边栏导航切换"""
        try:
            index = self.PAGE_IDS.index(page_id)
            self.content_stack.setCurrentIndex(index)
            logger.info(f"Switched to page: {page_id}")
        except ValueError:
            logger.warning(f"Unknown page: {page_id}")

    # ============================================================
    # 健康检查
    # ============================================================

    async def _check_health(self):
        from services.api_client import api
        try:
            result = await api.get("/health")
            if result.get("status") == "ok":
                self.status_label.setText("Backend connected")
            else:
                self.status_label.setText("Backend error")
        except Exception:
            self.status_label.setText("Backend offline")

    # ============================================================
    # 工具
    # ============================================================

    @staticmethod
    def _create_placeholder(title: str, phase: str) -> QWidget:
        w = QWidget()
        from PySide6.QtWidgets import QVBoxLayout
        layout = QVBoxLayout(w)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        t = QLabel(title)
        t.setStyleSheet(f"color: {Colors.text_primary}; font-size: 24px; font-weight: 600;")
        t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(t)

        d = QLabel(f"Coming in {phase}")
        d.setStyleSheet(f"color: {Colors.text_secondary}; font-size: 14px;")
        d.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(d)

        return w
