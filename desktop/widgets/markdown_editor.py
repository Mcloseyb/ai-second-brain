"""
Markdown 编辑器
---------------
简单的 Markdown 编辑组件，支持:
  - 语法高亮（基础）
  - Ctrl+S 自动保存
  - 标题字段 + 正文编辑区
  - 标签管理
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QTextEdit,
    QPushButton, QLabel, QFrame,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QKeySequence, QShortcut

from resources.styles.colors import Colors, Spacing, FontSize, Radius


class MarkdownEditor(QWidget):
    """Markdown 笔记编辑器"""

    save_requested = Signal(int, str, str)  # note_id, title, content

    def __init__(self):
        super().__init__()

        self._note_id: int | None = None
        self._dirty = False
        self._saving = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ---- 工具栏 ----
        toolbar = QWidget()
        toolbar.setFixedHeight(44)
        toolbar.setStyleSheet(f"""
            background: {Colors.bg_content};
            border-bottom: 1px solid {Colors.border_default};
        """)
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(Spacing.lg, Spacing.sm, Spacing.lg, Spacing.sm)

        # 标题
        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText("Note title...")
        self.title_input.setStyleSheet(f"""
            QLineEdit {{
                background: transparent;
                color: {Colors.text_primary};
                border: none;
                font-size: {FontSize.xl}px;
                font-weight: 700;
                padding: 0;
            }}
            QLineEdit::placeholder {{
                color: {Colors.text_tertiary};
            }}
        """)
        self.title_input.textChanged.connect(self._mark_dirty)
        toolbar_layout.addWidget(self.title_input)

        toolbar_layout.addStretch()

        self.save_btn = QPushButton("Save")
        self.save_btn.setProperty("cssClass", "primary")
        self.save_btn.setFixedHeight(30)
        self.save_btn.clicked.connect(self._on_save)
        toolbar_layout.addWidget(self.save_btn)

        # 标签编辑器区域
        self.tag_input = QLineEdit()
        self.tag_input.setPlaceholderText("Tags (comma separated)...")
        self.tag_input.setFixedHeight(30)
        self.tag_input.setStyleSheet(f"""
            QLineEdit {{
                background: transparent;
                color: {Colors.text_secondary};
                border: none;
                font-size: {FontSize.sm}px;
                padding: 0 16px;
            }}
            QLineEdit::placeholder {{
                color: {Colors.text_tertiary};
            }}
        """)
        toolbar_layout.addWidget(self.tag_input)

        layout.addWidget(toolbar)

        # 分割线
        divider = QFrame()
        divider.setStyleSheet(f"background: {Colors.border_default}; max-height: 1px; border: none;")
        divider.setFixedHeight(1)
        layout.addWidget(divider)

        # ---- 编辑区 ----
        self.editor = QTextEdit()
        self.editor.setPlaceholderText("Start writing... (Markdown supported)")
        self.editor.setStyleSheet(f"""
            QTextEdit {{
                background: {Colors.bg_content};
                color: {Colors.text_primary};
                border: none;
                padding: {Spacing.lg}px;
                font-size: {FontSize.lg}px;
                line-height: 1.7;
                selection-background-color: {Colors.accent_blue};
                selection-color: {Colors.text_inverse};
            }}
        """)
        font = QFont("Segoe UI", 14)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0.3)
        self.editor.setFont(font)
        self.editor.textChanged.connect(self._mark_dirty)
        layout.addWidget(self.editor)

        # Ctrl+S 快捷键
        save_shortcut = QShortcut(QKeySequence.StandardKey.Save, self)
        save_shortcut.activated.connect(self._on_save)

        # 保存状态标签
        self.status_label = QLabel("")
        self.status_label.setStyleSheet(f"""
            color: {Colors.text_tertiary};
            font-size: {FontSize.xs}px;
            padding: 4px 16px;
            border: none;
        """)
        layout.addWidget(self.status_label)

    # ============================================================
    # 数据加载/保存
    # ============================================================

    def load_note(self, note: dict):
        """加载笔记到编辑器"""
        self._note_id = note["id"]
        self._dirty = False

        self.title_input.blockSignals(True)
        self.editor.blockSignals(True)

        self.title_input.setText(note.get("title", ""))
        self.editor.setPlainText(note.get("content", ""))

        # 标签
        tags = note.get("tags", [])
        tag_text = ", ".join(t["name"] for t in tags)
        self.tag_input.setText(tag_text)

        self.title_input.blockSignals(False)
        self.editor.blockSignals(False)

        self._update_status()

    def clear(self):
        """清空编辑器"""
        self._note_id = None
        self._dirty = False
        self.title_input.clear()
        self.editor.clear()
        self.tag_input.clear()
        self._update_status()

    def _on_save(self):
        """保存笔记"""
        if self._saving:
            return

        title = self.title_input.text().strip() or "Untitled"
        content = self.editor.toPlainText()
        tags = [t.strip() for t in self.tag_input.text().split(",") if t.strip()]

        self._saving = True
        self.save_requested.emit(
            self._note_id if self._note_id else 0,
            title,
            content,
        )

    def save_done(self, note_id: int):
        """保存完成回调"""
        self._note_id = note_id
        self._dirty = False
        self._saving = False
        self._update_status()

    def save_failed(self):
        """保存失败回调"""
        self._saving = False
        self._update_status()

    # ============================================================
    # 内部
    # ============================================================

    def _mark_dirty(self):
        self._dirty = True
        self._update_status()

    def _update_status(self):
        if self._saving:
            self.status_label.setText("Saving...")
        elif self._dirty:
            self.status_label.setText("Unsaved changes")
        else:
            self.status_label.setText("Saved")
