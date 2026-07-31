"""
极简 PySide6 主窗口 — 纯 WebEngine 容器
--------------------------------------
窗口内只放一个全屏 QWebEngineView，所有 UI 交给 Vue3/Vuetify3 前端。
Qt 只负责：窗口外壳、WebView 容器、JS 通信桥、后端进程管理。

面试要点:
  Q: 为什么不用 Qt 原生控件而用 Web 技术？
  A: 1) Vue/Vuetify 生态更丰富，UI 更美观，迭代更快；
     2) 前后端完全分离，Web 工程师可以独立开发前端；
     3) 同一套前端代码未来可复用到 Electron 或 Web 版。
"""

import logging
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from PySide6.QtWidgets import QMainWindow, QVBoxLayout, QWidget
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtCore import QUrl, Qt

logger = logging.getLogger(__name__)

# 前端入口地址
DEV_URL = "http://localhost:5173"  # Vite 热更新开发服务器


class MainWindow(QMainWindow):
    """极简 WebView 容器窗口"""

    def __init__(self, bridge=None):
        """
        Args:
            bridge: QWebChannel 桥接对象（可选，生产/开发共用）
        """
        super().__init__()

        # ---- 窗口基础属性 ----
        self.setWindowTitle("AI Second Brain")
        self.resize(1280, 800)
        self.setMinimumSize(900, 600)

        # ---- 中心控件: 全屏 WebView ----
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.webview = QWebEngineView()
        # 启用右键菜单 — 由前端处理自定义上下文菜单
        self.webview.setContextMenuPolicy(Qt.ContextMenuPolicy.DefaultContextMenu)

        # ---- JS 通信桥 (QWebChannel) ----
        # 通过 bridge 对象暴露 Qt 端能力给 Vue 调用
        # 用法: 在 Vue 中用 window.bridge.xxx() 调用
        if bridge is not None:
            self.channel = QWebChannel()
            self.channel.registerObject("bridge", bridge)
            self.webview.page().setWebChannel(self.channel)

        layout.addWidget(self.webview)

        # ---- 加载前端 ----
        self._load_frontend()

    # ============================================================
    # 前端加载
    # ============================================================

    def _load_frontend(self):
        """
        智能加载前端:
          - 有 dist 打包 → 用本地 HTTP 服务加载（生产模式，可靠无 CORS 问题）
          - 无 dist 打包 → 连接 Vite 开发服务器（开发模式，热更新）

        为什么不用 file:// 直接打开 index.html？
          Vue/Vite 打包产物是 ES Module，Chromium 对 file:// 的模块加载
          有 CORS 限制，会白屏。用本地 HTTP 服务可彻底规避此问题。
        """
        dist_path = _find_dist()
        if dist_path is not None:
            # 生产模式: 启动本地 HTTP 服务托管 dist 目录
            port = _serve_dist(dist_path.parent)
            url = QUrl(f"http://127.0.0.1:{port}/")
            logger.info(f"生产模式: 本地服务 http://127.0.0.1:{port}/")
        else:
            # 开发模式: 加载 Vite 服务器
            url = QUrl(DEV_URL)
            logger.info(f"开发模式: 连接 {DEV_URL}")

        self.webview.load(url)

    # ============================================================
    # 对外接口
    # ============================================================

    def reload_page(self):
        """重新加载前端页面（开发调试用）"""
        self.webview.reload()

    def execute_js(self, code: str):
        """执行任意 JavaScript 代码（从 Qt 推消息到 Vue）"""
        self.webview.page().runJavaScript(code)

    def send_to_vue(self, event: str, data: dict):
        """
        向 Vue 前端推送事件消息

        用法:
            window.send_to_vue("sync_progress", {"percent": 50, "status": "syncing"})

        Vue 端通过 window.addEventListener 接收事件
        """
        import json
        payload = json.dumps(data, ensure_ascii=False)
        js_code = f"""
        (function() {{
            var event = new CustomEvent('qt:{event}', {{ detail: {payload} }});
            window.dispatchEvent(event);
        }})();
        """
        self.webview.page().runJavaScript(js_code)


# ============================================================
# 工具函数
# ============================================================

def _find_dist() -> Path | None:
    """
    查找 React 打包后的 dist/index.html

    查找顺序:
      1. desktop/../frontend/dist/index.html
      2. 可扩展更多路径
    """
    candidates = [
        Path(__file__).parent.parent / "frontend" / "dist" / "index.html",
        Path(__file__).parent.parent / "dist" / "index.html",
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def _serve_dist(dist_dir: Path) -> int:
    """
    在后台线程启动一个本地 HTTP 服务，托管 dist 打包目录。

    为什么需要？
      Qt 用 file:// 直接打开 index.html 时，ES Module 脚本会被
      Chromium 的 CORS 策略拦截（白屏）。用 HTTP 服务加载可以规避。

    返回端口号。服务在守护线程中运行，应用退出时自动结束。
    """
    # 静默日志: 屏蔽 http.server 的访问日志输出
    class QuietHandler(SimpleHTTPRequestHandler):
        def log_message(self, format, *args):  # noqa: A002
            logger.debug("HTTP: %s" % (format % args))

    # 指定服务目录为 dist 文件夹
    handler = partial(QuietHandler, directory=str(dist_dir))

    # 端口 0 = 让系统自动分配空闲端口，避免冲突
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    port = httpd.server_address[1]

    # 守护线程: 应用退出时自动销毁
    t = threading.Thread(target=httpd.serve_forever, daemon=True, name="dist-server")
    t.start()
    logger.info(f"dist 静态服务已启动: http://127.0.0.1:{port}/")
    return port
