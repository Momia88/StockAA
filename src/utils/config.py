"""
應用程式設定 — 使用 pydantic-settings 從 .env 讀取
"""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """全域設定（從 .env 讀取）"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # 資料庫路徑
    db_path: str = "./portfolio.db"

    # 手續費折扣（0.6 = 六折）
    brokerage_discount: float = 0.6

    # API 設定
    api_timeout: int = 15
    price_cache_ttl: int = 300  # 秒

    # 日誌等級
    log_level: str = "INFO"

    @property
    def db_url(self) -> str:
        """SQLAlchemy 連線字串"""
        return f"sqlite:///{self.db_path}"

    @property
    def resolved_db_path(self) -> Path:
        """解析絕對路徑"""
        return Path(self.db_path).expanduser().resolve()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """取得全域設定（singleton）"""
    return Settings()
