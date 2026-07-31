"""
FastAPI 应用入口
--------------
启动: uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
"""

import asyncio
import logging
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.config import settings
from app.database import init_db

# 配置日志
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ============================================================
# 后台同步任务配置（app.state 共享）
# ============================================================

DEFAULT_SYNC_INTERVAL = 30 * 60   # 30 分钟


# ============================================================
# 应用生命周期
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动/关闭时的处理"""
    # 启动时：初始化数据库
    logger.info(f"🚀 {settings.app_name} v{settings.app_version} 启动中...")
    init_db()
    logger.info(f"📁 数据库: {settings.database_path}")
    logger.info(f"📁 ChromaDB: {settings.chroma_path}")
    logger.info(f"📁 上传目录: {settings.upload_path}")

    # 确保默认笔记库存在 + 迁移旧笔记
    try:
        from app.database import SessionLocal
        from app.models.notebook import Notebook
        from app.models.note import Note

        db = SessionLocal()
        try:
            default_nb = db.query(Notebook).first()
            if not default_nb:
                default_nb = Notebook(name="我的笔记库", description="默认笔记库")
                db.add(default_nb)
                db.commit()
                db.refresh(default_nb)
                logger.info("📓 已创建默认笔记库")

            # 迁移 notebook_id 为 None 的旧笔记
            orphan_notes = db.query(Note).filter(Note.notebook_id.is_(None)).all()
            if orphan_notes:
                for note in orphan_notes:
                    note.notebook_id = default_nb.id
                db.commit()
                logger.info(f"📓 {len(orphan_notes)} 篇旧笔记已迁移到默认笔记库")
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"笔记库初始化失败（不影响使用）: {e}")

    # P3.1.5: 启动时自动索引未同步的笔记
    try:
        from app.database import SessionLocal
        from app.models.note import Note
        from app.core.rag_engine import rag_engine

        db = SessionLocal()
        try:
            all_notes = db.query(Note).all()
            unindexed = [
                n for n in all_notes
                if n.content and n.content.strip() and n.last_synced_at is None
            ]
            if unindexed:
                logger.info(f"🔍 发现 {len(unindexed)} 篇未索引笔记，开始批量向量化...")
                indexed = 0
                for note in unindexed:
                    try:
                        await rag_engine.index_note(note.id, note.title, note.content)
                        note.content_hash = Note.compute_content_hash(note.content)
                        note.last_synced_at = datetime.now(timezone.utc)
                        indexed += 1
                    except Exception as e:
                        logger.warning(f"索引笔记 {note.id} 失败: {e}")
                db.commit()
                logger.info(f"✅ 启动索引完成: {indexed}/{len(unindexed)} 篇")
            else:
                logger.info(f"✅ 所有笔记已索引 ({len(all_notes)} 篇)")
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"启动索引失败（不影响正常使用）: {e}")

    # 初始化后台同步状态
    app.state.auto_sync_enabled = False
    app.state.sync_interval = DEFAULT_SYNC_INTERVAL
    app.state.last_sync_at = None

    # 启动后台定时同步任务
    sync_task = asyncio.create_task(_periodic_sync_loop(app))
    app.state.sync_task = sync_task

    logger.info(f"✅ 初始化完成，监听 {settings.host}:{settings.port}")
    logger.info(f"⏰ 后台定时同步: {'启用' if app.state.auto_sync_enabled else '待启用'} "
                f"(间隔 {app.state.sync_interval // 60} 分钟)")

    yield  # 应用运行中...

    # 关闭时：取消后台任务
    logger.info("👋 应用正在关闭...")
    sync_task.cancel()
    try:
        await sync_task
    except asyncio.CancelledError:
        logger.info("后台同步任务已取消")


async def _periodic_sync_loop(app: FastAPI):
    """
    后台定时同步循环
    - 默认不自动运行，需要通过 API 启用
    - 启动后等 30s 再开始第一次
    """
    await asyncio.sleep(30)  # 启动缓冲

    while True:
        try:
            if app.state.auto_sync_enabled:
                from app.database import SessionLocal
                from app.services.sync_service import sync_service

                db = SessionLocal()
                try:
                    logger.info("⏰ 定时同步检查开始...")
                    report = await sync_service.sync_all(db)
                    app.state.last_sync_at = asyncio.get_event_loop().time()
                    if report.synced > 0 or report.failed > 0:
                        logger.info(
                            f"定时同步完成: {report.synced}更新 {report.skipped}跳过 "
                            f"{report.failed}失败 / {report.total}总计"
                        )
                finally:
                    db.close()
            else:
                logger.debug("定时同步未启用，跳过")

        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"定时同步异常: {e}")

        await asyncio.sleep(app.state.sync_interval)


# ============================================================
# 创建应用
# ============================================================

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="AI 协同个人知识库管理系统 — 后端 API",
    lifespan=lifespan,
)

# CORS 配置 — 允许桌面客户端跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 桌面应用从本地各种端口连接，开发阶段不限制
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# 注册路由
# ============================================================

from app.api.chat import router as chat_router
from app.api.notes import router as notes_router
from app.api.tags import router as tags_router
from app.api.documents import router as documents_router
from app.api.sync import router as sync_router
from app.api.notebooks import router as notebooks_router
from app.api.quiz import router as quiz_router

app.include_router(chat_router)
app.include_router(notes_router)
app.include_router(tags_router)
app.include_router(documents_router)
app.include_router(sync_router)
app.include_router(notebooks_router)
app.include_router(quiz_router)


# ============================================================
# 健康检查
# ============================================================

@app.get("/")
async def root():
    """根路径 — 服务健康检查"""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "status": "running",
    }


@app.get("/health")
async def health():
    """健康检查端点"""
    return {"status": "ok"}
