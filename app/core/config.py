"""
配置管理模块 - 使用 pydantic-settings 加载环境变量
"""

from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用全局配置"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # OpenAI
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-small"

    # 飞书
    feishu_app_id: Optional[str] = None
    feishu_app_secret: Optional[str] = None
    feishu_verification_token: Optional[str] = None
    feishu_event_encrypt_key: Optional[str] = None

    # 钉钉
    dingtalk_token: Optional[str] = None
    dingtalk_aes_key: Optional[str] = None
    dingtalk_app_key: Optional[str] = None
    dingtalk_app_secret: Optional[str] = None

    # 数据库
    sqlite_db_path: str = "data/memory.db"

    # 记忆
    short_term_max_messages: int = 20
    long_term_retrieval_top_k: int = 3

    # 日志
    log_level: str = "DEBUG"

    # 服务器
    host: str = "0.0.0.0"
    port: int = 8000

    # 网络搜索（可选）
    tavily_api_key: Optional[str] = None

    # Agent
    agent_max_iterations: int = 5


# 全局单例
settings = Settings()

if not settings.tavily_api_key:
    print("⚠️ TAVILY_API_KEY 未设置，网络搜索功能不可用。如需使用，请在 .env 中配置 TAVILY_API_KEY=your_key")

# 确保数据目录存在
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
SQLITE_PATH = DATA_DIR / "memory.db"

DATA_DIR.mkdir(parents=True, exist_ok=True)