"""
FastAPI 应用入口
--------------
启动: uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
"""

import logging

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
    logger.info(f"✅ 初始化完成，监听 {settings.host}:{settings.port}")

    yield  # 应用运行中...

    # 关闭时
    logger.info("👋 应用正在关闭...")


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

app.include_router(chat_router)
app.include_router(notes_router)
app.include_router(tags_router)


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
