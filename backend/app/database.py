"""
数据库引擎与 Session 管理
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import settings

# 共享的 Base — 所有模型继承自这个
Base = declarative_base()

# 创建引擎
# SQLite 需要 check_same_thread=False 才能在异步线程中使用
engine = create_engine(
    settings.database_url,
    echo=settings.debug,
    connect_args={"check_same_thread": False}
    if "sqlite" in settings.database_url
    else {},
)

# Session 工厂
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_db():
    """FastAPI 依赖注入 — 获取数据库 session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """创建所有表（首次启动时调用）"""
    # 确保数据目录存在
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)
    settings.chroma_path.mkdir(parents=True, exist_ok=True)
    settings.upload_path.mkdir(parents=True, exist_ok=True)

    Base.metadata.create_all(bind=engine)
