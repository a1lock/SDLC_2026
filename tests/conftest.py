import os
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app import validators
from app.config import normalize_database_url
from app.db import get_db
from app.main import app
from app.models import ROLE_ADMIN, ROLE_STOREKEEPER, Base, User
from app.security import get_throttle, hash_password
from scripts import seed

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "sqlite+pysqlite:///:memory:")
TODAY = date(2026, 12, 22)

ADMIN_LOGIN, ADMIN_PASSWORD = "admin", "Admin-pass-1"
KEEPER_LOGIN, KEEPER_PASSWORD = "keeper", "Keeper-pass-1"


@pytest.fixture(scope="session")
def engine():
    if TEST_DATABASE_URL.startswith("sqlite"):
        eng = create_engine(
            TEST_DATABASE_URL, poolclass=StaticPool, connect_args={"check_same_thread": False}
        )

        @event.listens_for(eng, "connect")
        def _configure_sqlite(dbapi_connection, _record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
            dbapi_connection.create_function(
                "lower", 1, lambda value: value.lower() if isinstance(value, str) else value
            )
    else:
        eng = create_engine(normalize_database_url(TEST_DATABASE_URL))
    Base.metadata.drop_all(eng)
    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)
    eng.dispose()


@pytest.fixture(autouse=True)
def clean_db(engine):
    yield
    with engine.begin() as connection:
        for table in reversed(Base.metadata.sorted_tables):
            connection.execute(table.delete())


@pytest.fixture(autouse=True)
def fixed_today(monkeypatch):
    monkeypatch.setattr(validators, "today", lambda: TODAY)


@pytest.fixture(autouse=True)
def fresh_throttle():
    get_throttle.cache_clear()
    yield
    get_throttle.cache_clear()


@pytest.fixture
def client(engine):
    def override_get_db():
        with Session(engine, expire_on_commit=False) as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def make_user(engine, login, password, role, is_active=True):
    with Session(engine) as session:
        session.add(
            User(
                login=login,
                password_hash=hash_password(password),
                role=role,
                is_active=is_active,
            )
        )
        session.commit()


def login_headers(client, login, password):
    response = client.post("/auth/login", json={"login": login, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def admin_headers(client, engine):
    make_user(engine, ADMIN_LOGIN, ADMIN_PASSWORD, ROLE_ADMIN)
    return login_headers(client, ADMIN_LOGIN, ADMIN_PASSWORD)


@pytest.fixture
def keeper_headers(client, engine):
    make_user(engine, KEEPER_LOGIN, KEEPER_PASSWORD, ROLE_STOREKEEPER)
    return login_headers(client, KEEPER_LOGIN, KEEPER_PASSWORD)


@pytest.fixture
def control(engine):
    with Session(engine) as session:
        seed.seed_control_example(session)
        session.commit()


def receipt(**overrides):
    data = {
        "order_number": "5",
        "order_date": "2026-12-10",
        "supplier_code": 103,
        "balance_account": "60.01",
        "doc_code": seed.DOC_INVOICE,
        "doc_number": "Н-5",
        "material_code": 1002,
        "material_account": "10.01",
        "unit_code": seed.METER,
        "quantity": "100",
        "unit_price": "250.00",
    }
    data.update(overrides)
    return data


def error_fields(response):
    return {item["loc"][-1] for item in response.json()["detail"]}
