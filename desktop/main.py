"""
AI Second Brain 桌面应用入口
--------------------------
自动启动 FastAPI 后端 → 等待就绪 → 打开 PySide6 WebView 窗口 → 加载 Vue3 前端。

启动方式:
  # 开发模式（前后端联动一键启动）
  python desktop/main.py

  # 手动启动后端（前端另起 Vite 热更新）
  uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
  python desktop/main.py --no-backend

面试要点:
  Q: 为什么用子进程启动后端而不是线程？
  A: uvicorn 内部有自己的事件循环和进程模型。
     用子进程启动可以完全隔离两个运行时，崩溃不互相影响。
     退出时 terminate() 子进程即可确保资源释放。
"""

import sys
import os
import signal
import subprocess
import time
import socket
import logging
import argparse
from pathlib import Path

# ---- 路径设置 ----
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("desktop")


# ============================================================
# 后端管理
# ============================================================

def _is_port_open(host: str = "127.0.0.1", port: int = 8000, timeout: float = 1.0) -> bool:
    """检查端口是否已被占用（即后端是否已启动）"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        result = sock.connect_ex((host, port))
        return result == 0
    finally:
        sock.close()


def _wait_for_backend(timeout: float = 30.0, interval: float = 0.5) -> bool:
    """
    轮询等待后端 8000 端口就绪

    Returns:
        True 如果后端就绪，False 如果超时
    """
    logger.info("等待后端就绪...")
    elapsed = 0.0
    while elapsed < timeout:
        if _is_port_open():
            logger.info(f"后端已就绪 (耗时 {elapsed:.1f}s)")
            # 额外等 0.5s 确保 uvicorn 完全初始化
            time.sleep(0.5)
            return True
        time.sleep(interval)
        elapsed += interval

    logger.error(f"后端启动超时 ({timeout}s)")
    return False


def start_backend() -> subprocess.Popen | None:
    """
    启动后端子进程 (uvicorn)

    Returns:
        Popen 对象（用于后续关闭），如果端口已被占用返回 None
    """
    # 如果已经有人在 8000 端口运行，跳过启动
    if _is_port_open():
        logger.info("后端已在 8000 端口运行，跳过启动")
        return None

    backend_dir = PROJECT_ROOT / "backend"
    logger.info("正在启动后端服务...")

    try:
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
            # Windows: 不显示控制台窗口
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        logger.info(f"后端已启动 (PID: {process.pid})")
        return process
    except Exception as e:
        logger.error(f"启动后端失败: {e}")
        return None


def stop_backend(process: subprocess.Popen | None):
    """安全关闭后端子进程"""
    if process is None:
        return
    logger.info(f"正在关闭后端 (PID: {process.pid})...")
    try:
        process.terminate()
        process.wait(timeout=5)
        logger.info("后端已关闭")
    except subprocess.TimeoutExpired:
        logger.warning("后端未响应，强制关闭")
        process.kill()
        process.wait()


# ============================================================
# 主入口
# ============================================================

def main():
    # ---- 解析命令行参数 ----
    parser = argparse.ArgumentParser(description="AI Second Brain 桌面客户端")
    parser.add_argument(
        "--no-backend",
        action="store_true",
        help="不启动后端（后端手动启动时使用）",
    )
    args = parser.parse_args()

    # ---- 启动后端 ----
    backend_process = None
    if not args.no_backend:
        backend_process = start_backend()
        if backend_process:
            if not _wait_for_backend():
                logger.error("后端启动失败，退出")
                stop_backend(backend_process)
                sys.exit(1)

    # ---- 创建 Qt 应用 ----
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt
    import qasync

    # 高 DPI 支持
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("AI Second Brain")
    app.setOrganizationName("AI-Second-Brain")

    # ---- 创建 JS 通信桥 ----
    # 在 WebView 加载之前创建 bridge，确保 WebChannel 注册可用
    from bridge import Bridge
    bridge = Bridge()

    # ---- 创建主窗口 (纯 WebView) ----
    from main_window import MainWindow
    window = MainWindow(bridge=bridge)

    # 把 bridge 关联到窗口，方便后续从 window.send_to_vue() 推送消息
    bridge.setParent(window)

    window.show()

    # ---- 事件循环 (qasync 桥接 Qt + asyncio) ----
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)

    # ---- 退出清理 ----
    def cleanup():
        stop_backend(backend_process)

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
    import asyncio
    main()
