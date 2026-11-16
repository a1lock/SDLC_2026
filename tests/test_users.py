from tests.conftest import login_headers


def new_user(**overrides):
    data = {"login": "ivanov", "password": "Ivanov-pass-1", "role": "storekeeper"}
    data.update(overrides)
    return data


def test_admin_creates_user_who_can_log_in(client, admin_headers):
    response = client.post("/users", json=new_user(), headers=admin_headers)
    assert response.status_code == 201
    body = response.json()
    assert body["login"] == "ivanov"
    assert body["is_active"] is True
    assert "password" not in body and "password_hash" not in body
    login_headers(client, "ivanov", "Ivanov-pass-1")


def test_duplicate_login_conflicts(client, admin_headers):
    assert client.post("/users", json=new_user(), headers=admin_headers).status_code == 201
    assert client.post("/users", json=new_user(), headers=admin_headers).status_code == 409


def test_weak_password_and_bad_role_are_rejected(client, admin_headers):
    short = client.post("/users", json=new_user(password="short"), headers=admin_headers)
    assert short.status_code == 422
    too_long = client.post("/users", json=new_user(password="я" * 40), headers=admin_headers)
    assert too_long.status_code == 422  # больше 72 байт
    bad_role = client.post("/users", json=new_user(role="boss"), headers=admin_headers)
    assert bad_role.status_code == 422


def test_storekeeper_cannot_manage_users(client, keeper_headers):
    assert client.get("/users", headers=keeper_headers).status_code == 403
    assert client.post("/users", json=new_user(), headers=keeper_headers).status_code == 403
    assert (
        client.patch("/users/1", json={"is_active": False}, headers=keeper_headers).status_code
        == 403
    )


def test_admin_lists_users_with_pagination(client, admin_headers):
    client.post("/users", json=new_user(), headers=admin_headers)
    response = client.get("/users", params={"page_size": 1}, headers=admin_headers)
    body = response.json()
    assert body["total"] == 2
    assert len(body["items"]) == 1


def test_admin_deactivates_user_and_changes_password(client, admin_headers):
    created = client.post("/users", json=new_user(), headers=admin_headers).json()
    url = f"/users/{created['id']}"

    changed = client.patch(url, json={"password": "New-password-2"}, headers=admin_headers)
    assert changed.status_code == 200
    login_headers(client, "ivanov", "New-password-2")

    disabled = client.patch(url, json={"is_active": False}, headers=admin_headers)
    assert disabled.json()["is_active"] is False
    response = client.post("/auth/login", json={"login": "ivanov", "password": "New-password-2"})
    assert response.status_code == 401


def test_admin_cannot_lock_himself_out(client, admin_headers):
    me = client.get("/auth/me", headers=admin_headers).json()
    url = f"/users/{me['id']}"
    assert client.patch(url, json={"is_active": False}, headers=admin_headers).status_code == 409
    assert client.patch(url, json={"role": "storekeeper"}, headers=admin_headers).status_code == 409


def test_patch_unknown_user(client, admin_headers):
    assert (
        client.patch("/users/9999", json={"is_active": False}, headers=admin_headers).status_code
        == 404
    )
