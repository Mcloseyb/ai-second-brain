"""
桌面应用入口
----------
启动后端子进程 + 创建 PySide6 主窗口。

启动方式:
    python desktop/main.py

    或者先手动启动后端:
    uvicorn app.main:app --app-dir backend --reload

    然后:
    python desktop/main.py --no-backend

面试要点:
  Q: 为什么桌面端要启动后端子进程？
  A: 这是"胖客户端"架构。后端提供 REST API，前端只管 UI。
     两者通过 HTTP 通信，完全解耦。
     如果以后要换成 Web 前端，后端一行代码不用改。
"""

import sys
import os
import signal
import subprocess
import logging
import argparse
from pathlib import Path

# 确保项目根目录在 sys.path 中
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("desktop")


def _load_stylesheet(app):
    """加载全局 QSS 主题样式"""
    qss_path = PROJECT_ROOT / "desktop" / "resources" / "styles" / "theme.qss"
    if qss_path.exists():
        with open(qss_path, "r", encoding="utf-8") as f:
            qss = f.read()
        app.setStyleSheet(qss)
        logger.info(f"Loaded stylesheet: {qss_path}")
    else:
        logger.warning(f"Stylesheet not found: {qss_path}")


def start_backend() -> subprocess.Popen | None:
    """启动后端子进程"""
    backend_dir = PROJECT_ROOT / "backend"

    # 检查是否已有人在 8000 端口运行
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    port_in_use = sock.connect_ex(("127.0.0.1", 8000)) == 0
    sock.close()

    if port_in_use:
        logger.info("后端已在 8000 端口运行，跳过启动")
        return None

    logger.info("正在启动后端服务...")
    try:
        # 用当前 Python 解释器启动 uvicorn
        python = sys.executable
        process = subprocess.Popen(
            [
                python, "-m", "uvicorn", "app.main:app",
                "--app-dir", str(backend_dir),
                "--host", "127.0.0.1",
                "--port", "8000",
                "--log-level", "info",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        logger.info(f"后端已启动 (PID: {process.pid})")
        return process
    except Exception as e:
        logger.error(f"启动后端失败: {e}")
        return None


def main():
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="AI Second Brain 桌面客户端")
    parser.add_argument(
        "--no-backend",
        action="store_true",
        help="不启动后端（后端已在运行）",
    )
    args = parser.parse_args()

    # 启动后端
    backend_process = None
    if not args.no_backend:
        backend_process = start_backend()
        if backend_process:
            # 等待后端启动
            import time
            time.sleep(2)

    # 启动 PySide6 应用（必须在导入 QApplication 之前设置）
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt
    import qasync

    # 高DPI支持
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("AI Second Brain")
    app.setOrganizationName("AI-Second-Brain")

    # 加载全局 QSS 样式表
    _load_stylesheet(app)

    # 注册自定义 CSS 属性（Qt 的 property selector 支持）
    # 允许 QSS 中使用 cssClass 选择器，如 QPushButton[cssClass="primary"]
    # PySide6 默认支持动态属性选择器，无需额外配置

    # 创建主窗口
    from main_window import MainWindow
    window = MainWindow()
    window.show()

    # 用 qasync 桥接 Qt 事件循环和 asyncio
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)

    # 退出时清理
    def cleanup():
        if backend_process:
            logger.info("正在关闭后端...")
            backend_process.terminate()
            try:
                backend_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                backend_process.kill()

    app.aboutToQuit.connect(cleanup)

    try:
        with loop:
            loop.run_forever()
    except KeyboardInterrupt:
        pass
    finally:
        cleanup()
        sys.exit(0)


if __name__ == "__main__":
    # 需要在这里导入 asyncio（qasync 需要）
    import asyncio
    main()
