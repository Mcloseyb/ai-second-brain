"""
数据库引擎与 Session 管理
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import settings

# 共享的 Base — 所有模型继承自这个
Base = declarative_base()

# 创建引擎（使用绝对路径，避免 CWD 不同导致找不到数据库文件）
_db_url = settings.database_url
if "sqlite" in _db_url:
    _db_url = f"sqlite:///{settings.database_path}"

engine = create_engine(
    _db_url,
    echo=settings.debug,
    connect_args={"check_same_thread": False}
    if "sqlite" in _db_url
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
    """创建所有表 + 执行迁移（首次启动时调用）"""
    # 导入所有模型，确保 Base.metadata 注册了所有表
    import app.models.conversation  # noqa: F401
    import app.models.message       # noqa: F401
    import app.models.note          # noqa: F401
    import app.models.tag           # noqa: F401
    import app.models.notebook      # noqa: F401
    import app.models.note_link     # noqa: F401
    import app.models.quiz          # noqa: F401
    import app.models.mastery       # noqa: F401
    import app.models.cluster       # noqa: F401
    import app.models.review        # noqa: F401
    import app.models.streak        # noqa: F401
    import app.models.bookmark      # noqa: F401
    import app.models.wrong_question  # noqa: F401

    # 确保数据目录存在
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)
    settings.chroma_path.mkdir(parents=True, exist_ok=True)
    settings.upload_path.mkdir(parents=True, exist_ok=True)

    Base.metadata.create_all(bind=engine)

    # SQLite 轻量迁移 — 给已有 notes 表补上 notebook_id 列
    if "sqlite" in _db_url:
        import logging
        _logger = logging.getLogger(__name__)
        with engine.connect() as conn:
            # 检查列是否存在
            result = conn.exec_driver_sql("PRAGMA table_info('notes')")
            columns = {row[1] for row in result}
            if "notebook_id" not in columns:
                _logger.info("迁移: 添加 notes.notebook_id 列")
                conn.exec_driver_sql(
                    "ALTER TABLE notes ADD COLUMN notebook_id INTEGER REFERENCES notebooks(id)"
                )
                conn.commit()
            if "deleted_at" not in columns:
                _logger.info("迁移: 添加 notes.deleted_at 列（软删除/回收站）")
                conn.exec_driver_sql(
                    "ALTER TABLE notes ADD COLUMN deleted_at TIMESTAMP"
                )
                conn.commit()
            # 给 review_logs 加 rating 列
            result = conn.exec_driver_sql("PRAGMA table_info('review_logs')")
            rl_columns = {row[1] for row in result}
            if "rating" not in rl_columns:
                _logger.info("迁移: 添加 review_logs.rating 列")
                conn.exec_driver_sql(
                    "ALTER TABLE review_logs ADD COLUMN rating VARCHAR(10)"
                )
                conn.commit()
