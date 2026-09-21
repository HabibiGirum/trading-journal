from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "TradePath"
    debug: bool = False
    secret_key: str = "change-me"
    database_url: str = f"sqlite:///{BASE_DIR / 'trading_journal.db'}"
    upload_dir: Path = BASE_DIR / "uploads"
    allowed_hosts: str = "*"
    session_https_only: bool = False
    max_image_mb: int = 8
    max_pdf_mb: int = 20

    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_trader: str = ""
    stripe_price_pro: str = ""
    public_base_url: str = ""
    enable_dev_billing: bool = False

    @property
    def host_list(self) -> list[str]:
        raw = self.allowed_hosts.strip()
        if not raw or raw == "*":
            return ["*"]
        return [item.strip() for item in raw.split(",") if item.strip()]

    @property
    def stripe_enabled(self) -> bool:
        return bool(self.stripe_secret_key and self.stripe_price_trader and self.stripe_price_pro)


@lru_cache
def get_settings() -> Settings:
    return Settings()
