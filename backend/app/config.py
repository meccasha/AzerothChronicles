"""Application configuration loaded from environment variables."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    app_env: str = "development"
    database_url: str = "postgresql+psycopg://azeroth:azeroth@localhost:5432/azeroth"
    # Public URL of the web app (used for invite links and OAuth redirects back to the UI).
    public_web_url: str = "http://localhost:3000"
    # Public URL where the API is reachable *by the browser* (for OAuth callback).
    public_api_url: str = "http://localhost:3000/api"
    allowed_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    session_cookie_name: str = "ac_session"
    session_ttl_hours: int = 24 * 14
    cookie_secure: bool = False

    # Fernet key (urlsafe base64, 32 bytes) used to encrypt OAuth tokens at rest.
    credentials_encryption_key: str = ""

    # Demo mode: seeds and exposes a fictional demo group + demo login.
    demo_mode: bool = True

    # Uploads
    upload_dir: str = "./uploads"
    max_upload_bytes: int = 8 * 1024 * 1024

    # Blizzard Battle.net
    blizzard_client_id: str = ""
    blizzard_client_secret: str = ""
    blizzard_default_region: str = "us"
    # "mock" uses fixture-backed adapter; "live" calls the real Battle.net API.
    blizzard_adapter: str = "mock"
    blizzard_locale: str = "en_US"

    # Background worker
    sync_interval_minutes: int = 360

    @property
    def blizzard_configured(self) -> bool:
        return bool(self.blizzard_client_id and self.blizzard_client_secret)


@lru_cache
def get_settings() -> Settings:
    return Settings()
