"""
应用配置管理
-----------
所有配置项通过环境变量读取，开发时用 .env 文件。
禁止在代码中硬编码密钥、URL 等敏感信息。
"""

from pathlib import Path
from pydantic_settings import BaseSettings


# 项目根目录（H:\agent）
PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()


class Settings(BaseSettings):
    """应用配置，自动从 .env 文件读取"""

    # --- LLM API ---
    deepseek_api_key: str = "sk-xxx"
    deepseek_base_url: str = "https://api.deepseek.com"

    # --- 数据库 ---
    database_url: str = "sqlite:///./data/app.db"

    # --- ChromaDB ---
    chroma_persist_directory: str = "./data/chroma_db"

    # --- 文件上传 ---
    upload_dir: str = "./data/uploads"
    max_upload_size_mb: int = 50

    # --- 应用 ---
    app_name: str = "AI Second Brain"
    app_version: str = "0.1.0"
    debug: bool = True
    host: str = "127.0.0.1"
    port: int = 8000

    # --- AI 参数 ---
    default_model: str = "deepseek-chat"
    embedding_model: str = "text-embedding-3-small"
    max_tokens: int = 4096
    temperature: float = 0.7

    class Config:
        env_file = str(PROJECT_ROOT / ".env")
        env_file_encoding = "utf-8"
        extra = "ignore"

    @property
    def database_path(self) -> Path:
        """返回数据库文件的绝对路径"""
        path = Path(self.database_url.replace("sqlite:///", ""))
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        return path

    @property
    def chroma_path(self) -> Path:
        """返回 ChromaDB 持久化目录的绝对路径"""
        path = Path(self.chroma_persist_directory)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        return path

    @property
    def upload_path(self) -> Path:
        """返回文件上传目录的绝对路径"""
        path = Path(self.upload_dir)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        return path


# 全局单例
settings = Settings()
