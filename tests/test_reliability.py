from sqlalchemy.exc import OperationalError

from app.db import get_db
from app.main import app


class BrokenSession:

    def __getattr__(self, name):
        def fail(*args, **kwargs):
            raise OperationalError("SELECT 1", {}, Exception("connection refused"))

        return fail


def test_health_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_health_reports_503_when_database_is_down(client):
    app.dependency_overrides[get_db] = BrokenSession
    response = client.get("/health")
    assert response.status_code == 503
    assert "База данных недоступна" in response.json()["detail"]


def test_api_returns_503_with_message_when_database_is_down(client, keeper_headers):
    app.dependency_overrides[get_db] = BrokenSession
    response = client.get("/materials/1001/suppliers/count", headers=keeper_headers)
    assert response.status_code == 503
    assert "База данных недоступна" in response.json()["detail"]


def test_index_and_openapi_are_available(client):
    assert client.get("/").status_code == 200
    schema = client.get("/openapi.json").json()
    paths = schema["paths"]
    for path in (
        "/auth/login",
        "/materials/{code}/suppliers/count",
        "/materials/{code}/suppliers",
        "/banks/suppliers/count",
        "/storage-units",
        "/materials/{code}/units",
        "/health",
    ):
        assert path in paths
