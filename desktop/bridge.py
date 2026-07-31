"""
Qt ↔ Vue JS 双向通信桥 (QWebChannel)
------------------------------------
通过 QWebChannel 将 Qt 端能力暴露为 JavaScript 对象，
Vue 通过 window.bridge.方法名() 调用 Qt 能力。

Qt 推送消息到 Vue 通过 MainWindow.send_to_vue() 方法。

架构:
  Vue 调用 Qt:   Vue → QWebChannel → bridge.py 方法 → Qt/系统能力
  Qt 推送 Vue:   Qt → main_window.send_to_vue() → window.dispatchEvent → Vue 监听

面试要点:
  Q: 为什么用 QWebChannel 而不是 WebSocket？
  A: QWebChannel 是 Qt 原生方案，无需额外端口、无需网络栈，
     在 WebEngine 进程内通过共享内存通信，延迟极低。
"""

import logging
import os
import json
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

logger = logging.getLogger(__name__)

# 项目根目录 (H:\agent)
PROJECT_ROOT = Path(__file__).parent.parent.resolve()


class Bridge(QObject):
    """
    暴露给 Vue 调用的 Qt 端能力

    Vue 调用示例:
      window.bridge.selectFile()           → 打开文件选择对话框
      window.bridge.readFolder(path)       → 读取文件夹内容
      window.bridge.minimizeWindow()       → 最小化窗口
      window.bridge.getAppVersion()        → 获取应用版本

    所有返回给 Vue 的方法使用 @Slot 装饰器 + 返回值
    异步结果通过 Signal 推送
    """

    # ---- 信号 (Qt → Vue 推送) ----
    fileSelected = Signal(str)        # 文件选择完成，传递文件路径
    folderRead = Signal(str)          # 文件夹读取结果 (JSON)
    agentProgress = Signal(str)       # Agent 执行进度 (JSON)
    syncStatus = Signal(str)          # 文档同步状态 (JSON)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._last_selected_file: str = ""  # 上次选中的文件路径

    # ============================================================
    # 文件操作 (Vue 调用 Qt)
    # ============================================================

    @Slot(result=str)
    def selectFile(self) -> str:
        """
        打开原生文件选择对话框，返回选中文件路径

        Vue 用法:
          const filePath = await window.bridge.selectFile()
          if (filePath) { /* 导入文件 */ }
        """
        from PySide6.QtWidgets import QFileDialog

        file_path, _ = QFileDialog.getOpenFileName(
            None,
            "选择文件",
            "",
            "文档 (*.md *.txt *.docx *.pdf);;所有文件 (*.*)",
        )
        if file_path:
            self._last_selected_file = file_path
            self.fileSelected.emit(file_path)
            logger.info(f"用户选择文件: {file_path}")
        return file_path

    @Slot(result=str)
    def selectFolder(self) -> str:
        """
        打开原生文件夹选择对话框

        Vue 用法:
          const folderPath = await window.bridge.selectFolder()
        """
        from PySide6.QtWidgets import QFileDialog

        folder = QFileDialog.getExistingDirectory(
            None, "选择文件夹", ""
        )
        if folder:
            logger.info(f"用户选择文件夹: {folder}")
        return folder

    @Slot(str, result=str)
    def readFolder(self, folder_path: str) -> str:
        """
        读取指定文件夹内容，返回 JSON 字符串

        Vue 用法:
          const result = await window.bridge.readFolder('/path/to/folder')
          const files = JSON.parse(result)

        返回格式:
          {
            "path": "/path/to/folder",
            "files": [{ "name": "note.md", "size": 1024, "modified": "2024-01-01" }, ...],
            "error": null
          }
        """
        p = Path(folder_path)
        if not p.exists():
            return json.dumps({"path": folder_path, "files": [], "error": "文件夹不存在"}, ensure_ascii=False)
        if not p.is_dir():
            return json.dumps({"path": folder_path, "files": [], "error": "不是文件夹"}, ensure_ascii=False)

        files = []
        try:
            for entry in sorted(p.iterdir()):
                if entry.name.startswith("."):
                    continue
                stat = entry.stat()
                files.append({
                    "name": entry.name,
                    "path": str(entry),
                    "is_dir": entry.is_dir(),
                    "size": stat.st_size,
                    "modified": stat.st_mtime,
                })
        except PermissionError:
            return json.dumps({"path": folder_path, "files": files, "error": "部分文件无权限"}, ensure_ascii=False)

        result = json.dumps({"path": folder_path, "files": files, "error": None}, ensure_ascii=False)
        self.folderRead.emit(result)
        return result

    # ============================================================
    # 窗口操作 (Vue 调用 Qt)
    # ============================================================

    @Slot()
    def minimizeWindow(self):
        """最小化窗口"""
        from PySide6.QtWidgets import QApplication
        for w in QApplication.topLevelWidgets():
            w.showMinimized()

    @Slot()
    def maximizeWindow(self):
        """最大化/还原窗口"""
        from PySide6.QtWidgets import QApplication
        for w in QApplication.topLevelWidgets():
            if w.isMaximized():
                w.showNormal()
            else:
                w.showMaximized()

    @Slot()
    def closeWindow(self):
        """关闭窗口（会触发清理流程）"""
        from PySide6.QtWidgets import QApplication
        QApplication.quit()

    # ============================================================
    # 应用信息 (Vue 调用 Qt)
    # ============================================================

    @Slot(result=str)
    def getAppVersion(self) -> str:
        """获取应用版本号"""
        return "0.2.0"

    @Slot(result=str)
    def getPlatform(self) -> str:
        """获取操作系统信息"""
        import platform
        return json.dumps({
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
        }, ensure_ascii=False)

    # ============================================================
    # 文件拖拽处理 (页面上拖入文件 → Bridge 读取 → 发送到后端)
    # ============================================================

    @Slot(str, result=str)
    def uploadFileToBackend(self, file_path: str) -> str:
        """
        将本地文件上传到后端导入 API
        返回 JSON: {"success": true, "note": {...}} 或 {"success": false, "error": "..."}

        Vue 用法（在拖拽回调中）:
          const result = JSON.parse(await window.bridge.uploadFileToBackend(filePath))
        """
        import asyncio
        import httpx

        async def _upload():
            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
                    with open(file_path, "rb") as f:
                        files = {"file": (os.path.basename(file_path), f)}
                        resp = await client.post(
                            "http://127.0.0.1:8000/api/documents/import",
                            data={"folder": "", "tags": ""},
                            files=files,
                        )
                        resp.raise_for_status()
                        return json.dumps({"success": True, **resp.json()}, ensure_ascii=False)
            except Exception as e:
                logger.error(f"文件上传失败: {e}")
                return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)

        # 在 Qt 环境中运行 asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                future = asyncio.run_coroutine_threadsafe(_upload(), loop)
                # 等待结果（同步桥接方法）
                return future.result(timeout=120)
            else:
                return asyncio.run(_upload())
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)

    # ============================================================
    # 后端状态检查
    # ============================================================

    @Slot(result=str)
    def checkBackendHealth(self) -> str:
        """
        检查后端是否就绪

        Vue 用法:
          const status = JSON.parse(await window.bridge.checkBackendHealth())
        """
        import httpx

        try:
            resp = httpx.get("http://127.0.0.1:8000/health", timeout=3)
            return json.dumps({"status": "ok", **resp.json()}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"status": "error", "error": str(e)}, ensure_ascii=False)
