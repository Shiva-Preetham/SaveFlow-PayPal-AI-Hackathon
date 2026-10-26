"""App settings, read from the repo-root .env (never committed)."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", extra="ignore")

    paypal_client_id: str = ""
    paypal_client_secret: str = ""
    paypal_base_url: str = "https://api-m.sandbox.paypal.com"
    currency: str = "USD"
    gemini_api_key: str = ""
    database_url: str = "sqlite:///./saveflow.db"
    frontend_origin: str = "http://localhost:5173"

    @property
    def paypal_configured(self) -> bool:
        return bool(self.paypal_client_id and self.paypal_client_secret)

    @property
    def gemini_configured(self) -> bool:
        return bool(self.gemini_api_key) and not self.gemini_api_key.startswith("paste_")


@lru_cache
def get_settings() -> Settings:
    return Settings()
