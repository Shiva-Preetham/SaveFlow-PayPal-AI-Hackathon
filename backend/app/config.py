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
    paypal_webhook_id: str = ""  # from developer.paypal.com -> your app -> Webhooks
    currency: str = "USD"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.1-flash-lite"  # first model tried
    # Tried in order when a model is rate-limited or overloaded; each has its own free-tier quota.
    gemini_fallback_models: str = ("gemini-2.5-flash-lite,gemini-3.5-flash-lite,gemini-flash-lite-latest,"
                                   "gemini-2.5-flash,gemini-3.5-flash,gemini-3.6-flash,gemini-3.8-flash,gemini-flash-latest")
    gemini_thinking_budget: int = 0  # 0 = off (2-4 s answers); -1 = model default
    database_url: str = "sqlite:///./saveflow.db"
    frontend_origin: str = "http://localhost:5173"
    public_url: str = "http://localhost:5173"  # where PayPal sends the buyer back after approving
    demo_mode: bool = True  # allows the "simulate webhook" button; real webhooks are always verified
    sync_catalogue_on_start: bool = True

    @property
    def paypal_configured(self) -> bool:
        return bool(self.paypal_client_id and self.paypal_client_secret) and \
            not self.paypal_client_id.startswith("paste_")

    @property
    def gemini_configured(self) -> bool:
        return bool(self.gemini_api_key) and not self.gemini_api_key.startswith("paste_")


@lru_cache
def get_settings() -> Settings:
    return Settings()
