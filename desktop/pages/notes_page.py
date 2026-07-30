"""
智能笔记页面
-----------
P2 阶段实现完整功能，当前为占位页面。
"""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Qt
from resources.styles.colors import Colors, FontSize


class NotesPage(QWidget):
    """笔记管理页面 — P2 实现"""

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel("Notes")
        title.setStyleSheet(f"""
            color: {Colors.text_primary};
            font-size: {FontSize.title}px;
            font-weight: 600;
        """)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        desc = QLabel("Full note management coming in Phase 2.\nCreate, edit, and organize your notes with AI assistance.")
        desc.setStyleSheet(f"color: {Colors.text_secondary}; font-size: {FontSize.lg}px;")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(desc)
