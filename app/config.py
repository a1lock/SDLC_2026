import os
from dataclasses import dataclass
from functools import lru_cache
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

MIN_SECRET_LENGTH = 32
MAX_TOKEN_MINUTES = 60


def normalize_database_url(url: str) -> str:
    for prefix in ("postgresql://", "postgres://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix) :]
    return url


@dataclass(frozen=True)
class Settings:
    database_url: str
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 60
    bcrypt_rounds: int = 12
    login_max_attempts: int = 5
    login_lock_minutes: int = 15
    timezone: str = "Europe/Moscow"
    log_level: str = "INFO"
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_timeout: int = 5


def _int_env(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        value = int(raw)
    except ValueError:
        raise RuntimeError(f"Переменная {name} должна быть целым числом") from None
    if not minimum <= value <= maximum:
        raise RuntimeError(f"Переменная {name} должна быть в диапазоне {minimum}–{maximum}")
    return value


@lru_cache
def get_settings() -> Settings:
    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        raise RuntimeError("Не задана переменная окружения DATABASE_URL")

    jwt_secret = os.environ.get("JWT_SECRET", "")
    if len(jwt_secret) < MIN_SECRET_LENGTH:
        raise RuntimeError(
            "Переменная JWT_SECRET должна быть задана "
            f"и содержать не менее {MIN_SECRET_LENGTH} символов"
        )

    timezone = os.environ.get("APP_TIMEZONE", "Europe/Moscow")
    try:
        ZoneInfo(timezone)
    except ZoneInfoNotFoundError:
        raise RuntimeError(f"Неизвестный часовой пояс APP_TIMEZONE: {timezone}") from None

    return Settings(
        database_url=normalize_database_url(database_url),
        jwt_secret=jwt_secret,
        access_token_minutes=_int_env("ACCESS_TOKEN_EXPIRE_MINUTES", 60, 1, MAX_TOKEN_MINUTES),
        bcrypt_rounds=_int_env("BCRYPT_ROUNDS", 12, 4, 16),
        login_max_attempts=_int_env("LOGIN_MAX_ATTEMPTS", 5, 1, 100),
        login_lock_minutes=_int_env("LOGIN_LOCK_MINUTES", 15, 1, 1440),
        timezone=timezone,
        log_level=os.environ.get("LOG_LEVEL", "INFO").upper(),
        db_pool_size=_int_env("DB_POOL_SIZE", 10, 1, 100),
        db_max_overflow=_int_env("DB_MAX_OVERFLOW", 20, 0, 200),
        db_pool_timeout=_int_env("DB_POOL_TIMEOUT", 5, 1, 60),
    )
