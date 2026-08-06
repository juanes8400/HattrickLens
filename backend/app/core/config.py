from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "local"
    database_url: str
    redis_url: str
    secret_key: str
    token_encryption_key: str
    jwt_access_ttl_minutes: int = 15
    jwt_refresh_ttl_days: int = 30
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
        "http://localhost:3002",
        "http://127.0.0.1:3002",
        "http://localhost:3003",
        "http://127.0.0.1:3003",
        "http://localhost:3004",
        "http://127.0.0.1:3004",
    ]
    frontend_url: str = "http://localhost:3000"

    chpp_consumer_key: str = ""
    chpp_consumer_secret: str = ""
    chpp_callback_url: str = ""
    chpp_user_agent: str = "HattrickLens/0.1.0"
    chpp_base_url: str = "https://chpp.hattrick.org"

    sentry_dsn: str = ""
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
