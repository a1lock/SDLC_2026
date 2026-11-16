from datetime import UTC, datetime, timedelta

import jwt
import pytest
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import ROLE_ADMIN, ROLE_STOREKEEPER, User
from app.security import get_throttle
from tests.conftest import (
    ADMIN_LOGIN,
    ADMIN_PASSWORD,
    KEEPER_LOGIN,
    KEEPER_PASSWORD,
    login_headers,
    make_user,
)


def attempt(client, login, password):
    return client.post("/auth/login", json={"login": login, "password": password})


def test_login_returns_token(client, engine):
    make_user(engine, KEEPER_LOGIN, KEEPER_PASSWORD, ROLE_STOREKEEPER)
    response = attempt(client, KEEPER_LOGIN, KEEPER_PASSWORD)
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["role"] == ROLE_STOREKEEPER
    assert body["expires_in"] == 3600
    claims = jwt.decode(body["access_token"], get_settings().jwt_secret, algorithms=["HS256"])
    assert claims["exp"] - claims["iat"] <= 3600


def test_me_returns_current_user(client, keeper_headers):
    response = client.get("/auth/me", headers=keeper_headers)
    assert response.status_code == 200
    assert response.json()["login"] == KEEPER_LOGIN
    assert "password_hash" not in response.json()


def test_wrong_password_and_unknown_login_look_the_same(client, engine):
    make_user(engine, KEEPER_LOGIN, KEEPER_PASSWORD, ROLE_STOREKEEPER)
    wrong = attempt(client, KEEPER_LOGIN, "not-the-password")
    unknown = attempt(client, "nobody", "whatever-password")
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


def test_inactive_user_cannot_log_in(client, engine):
    make_user(engine, KEEPER_LOGIN, KEEPER_PASSWORD, ROLE_STOREKEEPER, is_active=False)
    assert attempt(client, KEEPER_LOGIN, KEEPER_PASSWORD).status_code == 401


def test_lock_after_five_failures(client, engine):
    make_user(engine, KEEPER_LOGIN, KEEPER_PASSWORD, ROLE_STOREKEEPER)
    for _ in range(5):
        assert attempt(client, KEEPER_LOGIN, "bad-password").status_code == 401
    blocked = attempt(client, KEEPER_LOGIN, KEEPER_PASSWORD)
    assert blocked.status_code == 429
    assert 0 < int(blocked.headers["Retry-After"]) <= 15 * 60


def test_success_resets_failure_counter(client, engine):
    make_user(engine, KEEPER_LOGIN, KEEPER_PASSWORD, ROLE_STOREKEEPER)
    for _ in range(4):
        attempt(client, KEEPER_LOGIN, "bad-password")
    assert attempt(client, KEEPER_LOGIN, KEEPER_PASSWORD).status_code == 200
    for _ in range(4):
        assert attempt(client, KEEPER_LOGIN, "bad-password").status_code == 401
    assert attempt(client, KEEPER_LOGIN, KEEPER_PASSWORD).status_code == 200


def test_lock_expires_after_15_minutes(client, engine):
    make_user(engine, KEEPER_LOGIN, KEEPER_PASSWORD, ROLE_STOREKEEPER)
    now = [1000.0]
    get_throttle().clock = lambda: now[0]
    for _ in range(5):
        attempt(client, KEEPER_LOGIN, "bad-password")
    assert attempt(client, KEEPER_LOGIN, KEEPER_PASSWORD).status_code == 429
    now[0] += 15 * 60 + 1
    assert attempt(client, KEEPER_LOGIN, KEEPER_PASSWORD).status_code == 200


def test_protected_endpoints_require_token(client):
    assert client.get("/storage-units").status_code == 401
    assert client.get("/materials").status_code == 401
    response = client.get("/storage-units", headers={"Authorization": "Bearer garbage"})
    assert response.status_code == 401


def test_expired_token_is_rejected(client, engine):
    make_user(engine, KEEPER_LOGIN, KEEPER_PASSWORD, ROLE_STOREKEEPER)
    with Session(engine) as session:
        user_id = session.query(User).one().id
    expired = jwt.encode(
        {"sub": str(user_id), "exp": datetime.now(UTC) - timedelta(minutes=1)},
        get_settings().jwt_secret,
        algorithm="HS256",
    )
    response = client.get("/storage-units", headers={"Authorization": f"Bearer {expired}"})
    assert response.status_code == 401


def test_token_with_foreign_signature_is_rejected(client, engine):
    make_user(engine, KEEPER_LOGIN, KEEPER_PASSWORD, ROLE_STOREKEEPER)
    with Session(engine) as session:
        user_id = session.query(User).one().id
    forged = jwt.encode(
        {"sub": str(user_id), "exp": datetime.now(UTC) + timedelta(minutes=5)},
        "another-secret-another-secret-another-secret",
        algorithm="HS256",
    )
    response = client.get("/storage-units", headers={"Authorization": f"Bearer {forged}"})
    assert response.status_code == 401


def test_deactivated_user_loses_access_with_existing_token(client, engine):
    make_user(engine, ADMIN_LOGIN, ADMIN_PASSWORD, ROLE_ADMIN)
    make_user(engine, KEEPER_LOGIN, KEEPER_PASSWORD, ROLE_STOREKEEPER)
    keeper = login_headers(client, KEEPER_LOGIN, KEEPER_PASSWORD)
    assert client.get("/storage-units", headers=keeper).status_code == 200
    with Session(engine) as session:
        session.query(User).filter_by(login=KEEPER_LOGIN).one().is_active = False
        session.commit()
    assert client.get("/storage-units", headers=keeper).status_code == 401


@pytest.mark.parametrize(
    ("name", "value"),
    [("ACCESS_TOKEN_EXPIRE_MINUTES", "61"), ("JWT_SECRET", "short")],
)
def test_unsafe_settings_are_rejected(monkeypatch, name, value):
    monkeypatch.setenv(name, value)
    get_settings.cache_clear()
    try:
        with pytest.raises(RuntimeError):
            get_settings()
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()
