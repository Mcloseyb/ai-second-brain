"""
Notion 风格左侧边栏
------------------
布局:
  ┌──────────────┐
  │ Workspace    │  ← 工作区名称 + 切换按钮
  │ Switcher     │
  ├──────────────┤
  │ [Search...]  │  ← 搜索框
  ├──────────────┤
  │ NAVIGATION   │
  │  - Chat      │  ← 导航项（图标 + 文字）
  │  - Notes     │
  │  - Graph     │
  │  - Dashboard │
  ├──────────────┤
  │              │  ← 弹性空白
  ├──────────────┤
  │ User avatar  │  ← 用户区域
  │ Settings     │
  └──────────────┘

宽度: 240px 固定，可拖拽调整（后期实现）
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QFrame, QSizePolicy, QSpacerItem,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QIcon

from resources.styles.colors import Colors, Spacing, Radius, FontSize


class SidebarItem(QPushButton):
    """侧边栏导航项 — 可选中状态"""

    clicked_with_id = Signal(str)

    def __init__(self, item_id: str, label: str, icon_text: str = ""):
        super().__init__()
        self.item_id = item_id
        self._label = label
        self._icon_text = icon_text
        self._active = False

        display = f"  {icon_text}  {label}" if icon_text else f"  {label}"
        self.setText(display)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self.setStyleSheet(self._style(active=False))
        self.setFixedHeight(36)
        self.clicked.connect(lambda: self.clicked_with_id.emit(self.item_id))

    def set_active(self, active: bool):
        self._active = active
        self.setStyleSheet(self._style(active))

    @staticmethod
    def _style(active: bool) -> str:
        if active:
            return f"""
                QPushButton {{
                    background: {Colors.sidebar_item_active};
                    color: {Colors.text_primary};
                    border: none;
                    border-radius: {Radius.md}px;
                    text-align: left;
                    padding-left: 8px;
                    font-size: {FontSize.md}px;
                    font-weight: 600;
                }}
            """
        return f"""
            QPushButton {{
                background: transparent;
                color: {Colors.text_secondary};
                border: none;
                border-radius: {Radius.md}px;
                text-align: left;
                padding-left: 8px;
                font-size: {FontSize.md}px;
            }}
            QPushButton:hover {{
                background: {Colors.sidebar_item_hover};
                color: {Colors.text_primary};
            }}
        """


class Sidebar(QWidget):
    """左侧边栏"""

    # 导航切换信号
    navigation_changed = Signal(str)

    ITEMS = [
        ("chat", "Chat", "Chat"),
        ("notes", "Notes", "Notes"),
        ("graph", "Graph", "Graph"),
        ("dashboard", "Dashboard", "Dashboard"),
    ]

    def __init__(self):
        super().__init__()
        self.setFixedWidth(240)
        self.setStyleSheet(f"background: {Colors.bg_sidebar};")

        self._items: dict[str, SidebarItem] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(Spacing.sm, Spacing.sm, Spacing.sm, Spacing.sm)
        layout.setSpacing(Spacing.xs)

        # ---- 工作区切换器 ----
        workspace = QPushButton("AI Second Brain")
        workspace.setCursor(Qt.CursorShape.PointingHandCursor)
        workspace.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {Colors.text_primary};
                border: none;
                border-radius: {Radius.md}px;
                text-align: left;
                padding: 10px 12px;
                font-size: {FontSize.lg}px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: {Colors.sidebar_item_hover};
            }}
        """)
        workspace.setFixedHeight(40)
        layout.addWidget(workspace)

        # ---- 搜索框 ----
        search = QLineEdit()
        search.setPlaceholderText("Search...")
        search.setStyleSheet(f"""
            QLineEdit {{
                background: {Colors.bg_input};
                color: {Colors.text_primary};
                border: 1px solid {Colors.border_default};
                border-radius: {Radius.md}px;
                padding: 8px 12px;
                font-size: {FontSize.sm}px;
                margin: {Spacing.xs}px 0;
            }}
            QLineEdit:focus {{
                border-color: {Colors.border_focus};
                background: {Colors.bg_input_focus};
            }}
            QLineEdit::placeholder {{
                color: {Colors.text_tertiary};
            }}
        """)
        search.setFixedHeight(34)
        layout.addWidget(search)

        # ---- 分割线 ----
        divider1 = QFrame()
        divider1.setProperty("cssClass", "divider")
        divider1.setStyleSheet(f"background: {Colors.sidebar_divider}; max-height: 1px; border: none; margin: {Spacing.xs}px 0;")
        divider1.setFixedHeight(1)
        layout.addWidget(divider1)

        # ---- 导航项 ----
        nav_label = QLabel("NAVIGATION")
        nav_label.setStyleSheet(f"""
            color: {Colors.text_tertiary};
            font-size: {FontSize.xs}px;
            font-weight: 600;
            letter-spacing: 1px;
            padding: {Spacing.sm}px {Spacing.sm}px {Spacing.xs}px {Spacing.sm}px;
        """)
        layout.addWidget(nav_label)

        for item_id, icon, label in self.ITEMS:
            btn = SidebarItem(item_id, label, icon)
            btn.clicked_with_id.connect(self._on_item_clicked)
            self._items[item_id] = btn
            layout.addWidget(btn)

        # ---- 弹性空间 ----
        layout.addSpacerItem(QSpacerItem(
            20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding
        ))

        # ---- 底部分割线 ----
        divider2 = QFrame()
        divider2.setStyleSheet(f"background: {Colors.sidebar_divider}; max-height: 1px; border: none;")
        divider2.setFixedHeight(1)
        layout.addWidget(divider2)

        # ---- 用户区域 ----
        user_section = QWidget()
        user_section.setStyleSheet(f"background: transparent;")
        user_layout = QHBoxLayout(user_section)
        user_layout.setContentsMargins(Spacing.sm, Spacing.sm, Spacing.sm, Spacing.sm)

        # 头像占位
        avatar = QLabel("U")
        avatar.setFixedSize(28, 28)
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar.setStyleSheet(f"""
            background: {Colors.accent_blue};
            color: {Colors.text_inverse};
            border-radius: {Radius.full}px;
            font-size: {FontSize.sm}px;
            font-weight: 600;
        """)
        user_layout.addWidget(avatar)

        user_name = QLabel("User")
        user_name.setStyleSheet(f"color: {Colors.text_primary}; font-size: {FontSize.sm}px;")
        user_layout.addWidget(user_name)

        user_layout.addStretch()

        # 设置按钮
        settings_btn = QPushButton("Settings")
        settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        settings_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {Colors.text_tertiary};
                border: none;
                font-size: {FontSize.xs}px;
            }}
            QPushButton:hover {{
                color: {Colors.text_primary};
            }}
        """)
        user_layout.addWidget(settings_btn)

        layout.addWidget(user_section)

        # 默认选中 Chat
        self.set_active_item("chat")

    def _on_item_clicked(self, item_id: str):
        """导航项点击"""
        self.set_active_item(item_id)
        self.navigation_changed.emit(item_id)

    def set_active_item(self, item_id: str):
        """设置当前激活的导航项"""
        for iid, btn in self._items.items():
            btn.set_active(iid == item_id)
