"""
笔记树形列表
-----------
显示所有笔记的列表，支持搜索和按标签筛选。
选中笔记后发出信号，通知编辑器加载内容。
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLineEdit, QListWidget, QListWidgetItem, QLabel,
    QHBoxLayout, QPushButton,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from resources.styles.colors import Colors, Spacing, FontSize, Radius


class NoteTreeWidget(QWidget):
    """笔记列表组件"""

    note_selected = Signal(int)   # 选中笔记 ID
    note_created = Signal()       # 请求创建新笔记

    def __init__(self):
        super().__init__()
        self.setFixedWidth(260)
        self.setStyleSheet(f"background: {Colors.bg_sidebar};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(Spacing.md, Spacing.md, Spacing.md, Spacing.md)
        layout.setSpacing(Spacing.sm)

        # 标题
        header_layout = QHBoxLayout()
        title = QLabel("Notes")
        title.setStyleSheet(f"""
            color: {Colors.text_primary};
            font-size: {FontSize.md}px;
            font-weight: 600;
            border: none;
        """)
        header_layout.addWidget(title)
        header_layout.addStretch()

        self.new_btn = QPushButton("+")
        self.new_btn.setFixedSize(28, 28)
        self.new_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.new_btn.setStyleSheet(f"""
            QPushButton {{
                background: {Colors.bg_card};
                color: {Colors.text_primary};
                border: none;
                border-radius: {Radius.md}px;
                font-size: 18px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: {Colors.accent_blue};
                color: {Colors.text_inverse};
            }}
        """)
        self.new_btn.clicked.connect(self.note_created.emit)
        header_layout.addWidget(self.new_btn)
        layout.addLayout(header_layout)

        # 搜索框
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Filter notes...")
        self.search_box.setStyleSheet(f"""
            QLineEdit {{
                background: {Colors.bg_input};
                color: {Colors.text_primary};
                border: 1px solid {Colors.border_default};
                border-radius: {Radius.md}px;
                padding: 6px 10px;
                font-size: {FontSize.sm}px;
            }}
            QLineEdit:focus {{
                border-color: {Colors.border_focus};
            }}
            QLineEdit::placeholder {{
                color: {Colors.text_tertiary};
            }}
        """)
        self.search_box.setFixedHeight(30)
        self.search_box.textChanged.connect(self._on_search)
        layout.addWidget(self.search_box)

        # 笔记列表
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet(f"""
            QListWidget {{
                background: transparent;
                border: none;
                outline: none;
            }}
            QListWidget::item {{
                color: {Colors.text_secondary};
                padding: 8px 10px;
                border-radius: {Radius.sm}px;
                margin: 1px 0;
            }}
            QListWidget::item:hover {{
                color: {Colors.text_primary};
                background: {Colors.bg_card_hover};
            }}
            QListWidget::item:selected {{
                color: {Colors.text_primary};
                background: {Colors.sidebar_item_active};
            }}
        """)
        self.list_widget.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.list_widget)

        # 数据
        self._notes: list[dict] = []

    # ============================================================
    # 数据加载
    # ============================================================

    async def load_notes(self, search: str = ""):
        """从 API 加载笔记列表"""
        from services.api_client import api
        try:
            result = await api.get("/api/notes", params={
                "search": search,
                "page_size": 100,
            })
            self._notes = result.get("notes", [])
            self._refresh_list()
        except Exception:
            pass

    def _refresh_list(self):
        """刷新列表显示"""
        self.list_widget.clear()
        for note in self._notes:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, note["id"])

            # 标题 + 日期
            title = note["title"] or "Untitled"
            date = note.get("updated_at", "")[:10] if note.get("updated_at") else ""

            display = f"{title}\n"
            if date:
                display += f"  {date}"

            tags_str = ""
            if note.get("tags"):
                tags_str = " ".join(f"#{t['name']}" for t in note["tags"])

            item.setText(f"{title}\n  {tags_str}")
            self.list_widget.addItem(item)

    # ============================================================
    # 事件
    # ============================================================

    def _on_search(self, text: str):
        import asyncio
        asyncio.ensure_future(self.load_notes(search=text))

    def _on_item_clicked(self, item: QListWidgetItem):
        note_id = item.data(Qt.ItemDataRole.UserRole)
        if note_id:
            self.note_selected.emit(note_id)
