import math
import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from functools import lru_cache

import bcrypt
import jwt

from app.config import get_settings
from app.models import User

BCRYPT_MAX_BYTES = 72
MAX_TRACKED_LOGINS = 10_000


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt(rounds=get_settings().bcrypt_rounds)
    return bcrypt.hashpw(password.encode(), salt).decode()


def verify_password(password: str, password_hash: str) -> bool:
    raw = password.encode()
    if len(raw) > BCRYPT_MAX_BYTES:
        return False
    try:
        return bcrypt.checkpw(raw, password_hash.encode())
    except ValueError:
        return False


@lru_cache
def dummy_hash() -> str:
    return hash_password("dummy-password-for-timing")


def create_access_token(user: User) -> tuple[str, int]:
    settings = get_settings()
    now = datetime.now(UTC)
    lifetime = timedelta(minutes=settings.access_token_minutes)
    payload = {
        "sub": str(user.id),
        "role": user.role,
        "iat": now,
        "exp": now + lifetime,
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, int(lifetime.total_seconds())


def decode_access_token(token: str) -> dict:
    settings = get_settings()
    return jwt.decode(
        token,
        settings.jwt_secret,
        algorithms=[settings.jwt_algorithm],
        options={"require": ["exp", "sub"]},
    )


class LoginThrottle:

    def __init__(
        self,
        max_attempts: int,
        lock_seconds: int,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.max_attempts = max_attempts
        self.lock_seconds = lock_seconds
        self.clock = clock
        self._guard = threading.Lock()
        self._failures: dict[str, int] = {}
        self._locked_until: dict[str, float] = {}

    def seconds_locked(self, login: str) -> int:
        key = login.lower()
        now = self.clock()
        with self._guard:
            until = self._locked_until.get(key)
            if until is None:
                return 0
            if now >= until:
                del self._locked_until[key]
                self._failures.pop(key, None)
                return 0
            return math.ceil(until - now)

    def register_failure(self, login: str) -> None:
        key = login.lower()
        now = self.clock()
        with self._guard:
            count = self._failures.get(key, 0) + 1
            if count >= self.max_attempts:
                self._failures.pop(key, None)
                self._locked_until[key] = now + self.lock_seconds
            else:
                self._failures[key] = count
            self._prune(now)

    def reset(self, login: str) -> None:
        key = login.lower()
        with self._guard:
            self._failures.pop(key, None)
            self._locked_until.pop(key, None)

    def clear(self) -> None:
        with self._guard:
            self._failures.clear()
            self._locked_until.clear()

    def _prune(self, now: float) -> None:
        if len(self._failures) + len(self._locked_until) <= MAX_TRACKED_LOGINS:
            return
        for key in [k for k, until in self._locked_until.items() if until <= now]:
            del self._locked_until[key]
        while len(self._failures) > MAX_TRACKED_LOGINS // 2:
            del self._failures[next(iter(self._failures))]


@lru_cache
def get_throttle() -> LoginThrottle:
    settings = get_settings()
    return LoginThrottle(settings.login_max_attempts, settings.login_lock_minutes * 60)
