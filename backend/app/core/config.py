from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "local"
    database_url: str
    # Declarado pero sin uso hoy: la caché vive en memoria del proceso. Es
    # opcional para no exigir un Redis al desplegar.
    redis_url: str = ""
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


def _normaliza_postgres(url: str) -> str:
    """Deja la URL como la quiere el driver asíncrono.

    Los proveedores de Postgres (Neon, Render, Railway) dan la cadena en el
    formato de `psycopg`, que no vale aquí y falla de una forma que no ayuda
    nada a entender qué pasa:

      · `postgresql://…`  →  SQLAlchemy elige un driver SÍNCRONO y revienta
        con "The asyncio extension requires an async driver".
      · `?sslmode=require` →  `asyncpg` no conoce ese parámetro y responde
        "invalid dsn: invalid connection option 'sslmode'".

    Se traduce aquí en vez de pedirle al que despliega que edite la cadena a
    mano: es un paso que se olvida, y el error no dice que sobre un parámetro.
    """
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+asyncpg://" + url[len("postgresql://"):]
    if "+asyncpg" in url and "sslmode=" in url:
        partes = url.split("?", 1)
        opciones = [
            o for o in partes[1].split("&")
            if not o.startswith("sslmode=") and not o.startswith("channel_binding=")
        ]
        # `sslmode=require` en asyncpg se pide con `ssl=require`.
        opciones.append("ssl=require")
        url = partes[0] + "?" + "&".join(opciones)
    return url


@lru_cache
def get_settings() -> Settings:
    ajustes = Settings()
    return ajustes.model_copy(
        update={"database_url": _normaliza_postgres(ajustes.database_url)}
    )


settings = get_settings()
