"""
智能笔记页面
-----------
左侧: 笔记树形列表（搜索 + 筛选 + 导入 + 同步按钮）
右侧: Markdown 编辑器
"""

import asyncio
import logging

from PySide6.QtWidgets import QWidget, QHBoxLayout, QSplitter, QFileDialog, QMessageBox
from PySide6.QtCore import Qt

from widgets.note_tree import NoteTreeWidget
from widgets.markdown_editor import MarkdownEditor
from resources.styles.colors import Colors, Spacing

logger = logging.getLogger(__name__)


class NotesPage(QWidget):
    """笔记管理页面"""

    def __init__(self):
        super().__init__()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ---- 分割器（可拖拽调整左右比例）----
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setStyleSheet(f"""
            QSplitter::handle {{
                background: {Colors.border_default};
                width: 1px;
            }}
        """)

        # 左侧 — 笔记列表
        self.note_tree = NoteTreeWidget()
        self.note_tree.note_selected.connect(self._on_note_selected)
        self.note_tree.note_created.connect(self._on_new_note)
        self.note_tree.import_requested.connect(self._on_import)
        self.note_tree.sync_requested.connect(self._on_sync)
        splitter.addWidget(self.note_tree)

        # 右侧 — 编辑器
        self.editor = MarkdownEditor()
        self.editor.save_requested.connect(self._on_save_requested)
        splitter.addWidget(self.editor)

        # 初始比例: 260px 列表 | 剩余给编辑器
        splitter.setSizes([260, 740])

        layout.addWidget(splitter)

        # 加载笔记列表
        asyncio.ensure_future(self.note_tree.load_notes())

    # ============================================================
    # 事件处理
    # ============================================================

    def _on_note_selected(self, note_id: int):
        """选中了一个笔记 — 加载到编辑器"""
        asyncio.ensure_future(self._load_note(note_id))

    async def _load_note(self, note_id: int):
        from services.api_client import api
        try:
            result = await api.get(f"/api/notes/{note_id}")
            note = result.get("note", {})
            self.editor.load_note(note)
        except Exception as e:
            logger.error(f"Failed to load note {note_id}: {e}")

    def _on_new_note(self):
        """创建新笔记"""
        asyncio.ensure_future(self._create_new_note())

    def _on_import(self):
        """导入文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Import File",
            "",
            "Documents (*.md *.txt *.docx *.pdf);;All Files (*.*)",
        )
        if file_path:
            asyncio.ensure_future(self._import_file(file_path))

    def _on_sync(self):
        """手动同步到向量库"""
        asyncio.ensure_future(self._sync_now())

    async def _create_new_note(self):
        from services.api_client import api
        try:
            result = await api.post("/api/notes", {"title": "Untitled", "content": ""})
            note = result.get("note", {})
            # 刷新列表
            await self.note_tree.load_notes()
            # 加载到编辑器
            self.editor.load_note(note)
        except Exception as e:
            logger.error(f"Failed to create note: {e}")

    def _on_save_requested(self, note_id: int, title: str, content: str):
        """保存笔记请求"""
        asyncio.ensure_future(self._save_note(note_id, title, content))

    async def _save_note(self, note_id: int, title: str, content: str):
        from services.api_client import api
        try:
            tags = [t.strip() for t in self.editor.tag_input.text().split(",") if t.strip()]

            if note_id == 0:
                # 新笔记 — 创建
                result = await api.post("/api/notes", {
                    "title": title,
                    "content": content,
                    "tags": tags,
                })
                note = result.get("note", {})
                self.editor.save_done(note["id"])
                await self.note_tree.load_notes()
            else:
                # 已有笔记 — 更新
                await api.put(f"/api/notes/{note_id}", {
                    "title": title,
                    "content": content,
                    "tags": tags,
                })
                self.editor.save_done(note_id)
        except Exception as e:
            logger.error(f"Failed to save note: {e}")
            self.editor.save_failed()

    async def _import_file(self, file_path: str):
        """导入文件到笔记库"""
        from services.api_client import api
        try:
            result = await api.upload("/api/documents/import", file_path, {"folder": "", "tags": ""})
            note = result.get("note", {})
            synced = result.get("synced", False)
            logger.info(f"Imported: {note['title']} (synced={synced})")
            await self.note_tree.load_notes()
            QMessageBox.information(
                self, "Import Success",
                f"Imported: {note['title']}\nSynced to vector DB: {'Yes' if synced else 'No'}",
            )
        except Exception as e:
            logger.error(f"Failed to import file: {e}")
            QMessageBox.warning(self, "Import Failed", str(e))

    async def _sync_now(self):
        """手动触发同步"""
        from services.api_client import api
        try:
            result = await api.post("/api/sync/now")
            report = result.get("report", {})
            msg = f"Total: {report['total']}\nSynced: {report['synced']}\nSkipped: {report['skipped']}\nFailed: {report['failed']}"
            logger.info(f"Sync done: {msg}")
            QMessageBox.information(self, "Sync Complete", msg)
        except Exception as e:
            logger.error(f"Failed to sync: {e}")
            QMessageBox.warning(self, "Sync Failed", str(e))
