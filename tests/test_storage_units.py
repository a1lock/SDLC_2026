import pytest

from tests.conftest import error_fields, receipt


def test_cost_is_rounded_to_kopecks(client, control, keeper_headers):
    cases = [
        ({"quantity": "0.005", "unit_price": "1.00"}, "0.01"),
        ({"quantity": "0.333", "unit_price": "10.01"}, "3.33"),
        ({"quantity": "2", "unit_price": "0"}, "0.00"),
    ]
    for number, (override, expected) in enumerate(cases, start=10):
        payload = receipt(order_number=str(number), **override)
        response = client.post("/storage-units", json=payload, headers=keeper_headers)
        assert response.status_code == 201, response.text
        assert response.json()["cost"] == expected


def test_numbers_in_json_are_accepted(client, control, keeper_headers):
    payload = receipt(quantity=100, unit_price=250.5)
    response = client.post("/storage-units", json=payload, headers=keeper_headers)
    assert response.status_code == 201
    body = response.json()
    assert body["quantity"] == "100.000"
    assert body["unit_price"] == "250.50"
    assert body["cost"] == "25050.00"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("order_number", ""),
        ("order_number", "1" * 21),
        ("order_date", "2026-12-23"),
        ("order_date", "10.12.2026"),
        ("balance_account", "6"),
        ("balance_account", "60.1"),
        ("balance_account", "60.01.01"),
        ("material_account", "abc"),
        ("doc_number", ""),
        ("doc_number", "Н" * 31),
        ("quantity", "0"),
        ("quantity", "1.0005"),
        ("quantity", "100000000000.000"),
        ("unit_price", "-0.01"),
        ("unit_price", "10.001"),
        ("supplier_code", 0),
        ("supplier_code", 99999999999),
    ],
)
def test_format_and_range_violations_give_422(client, control, keeper_headers, field, value):
    response = client.post("/storage-units", json=receipt(**{field: value}), headers=keeper_headers)
    assert response.status_code == 422
    assert field in error_fields(response)
    assert client.get("/storage-units", headers=keeper_headers).json()["total"] == 4


def test_all_missing_references_are_reported_together(client, control, keeper_headers):
    payload = receipt(supplier_code=999, doc_code=999, material_code=9999, unit_code=4242)
    response = client.post("/storage-units", json=payload, headers=keeper_headers)
    assert response.status_code == 422
    assert error_fields(response) == {"supplier_code", "doc_code", "material_code", "unit_code"}


def test_order_may_be_dated_today(client, control, keeper_headers):
    response = client.post(
        "/storage-units", json=receipt(order_date="2026-12-22"), headers=keeper_headers
    )
    assert response.status_code == 201


def test_same_order_number_on_another_date_is_allowed(client, control, keeper_headers):
    payload = receipt(order_number="1", order_date="2026-12-11")
    assert client.post("/storage-units", json=payload, headers=keeper_headers).status_code == 201


def test_list_is_paginated_newest_first(client, control, keeper_headers):
    page1 = client.get("/storage-units", params={"page_size": 3}, headers=keeper_headers).json()
    assert page1["total"] == 4
    assert page1["page"] == 1 and page1["page_size"] == 3
    assert [u["order_number"] for u in page1["items"]] == ["4", "3", "2"]
    assert page1["items"][0]["cost"] == "122500.00"

    page2 = client.get(
        "/storage-units", params={"page_size": 3, "page": 2}, headers=keeper_headers
    ).json()
    assert [u["order_number"] for u in page2["items"]] == ["1"]


def test_list_filters(client, control, keeper_headers):
    by_material = client.get(
        "/storage-units", params={"material_code": 1002}, headers=keeper_headers
    )
    assert by_material.json()["total"] == 1
    by_supplier = client.get(
        "/storage-units", params={"supplier_code": 101}, headers=keeper_headers
    )
    assert by_supplier.json()["total"] == 2
    huge = client.get(
        "/storage-units", params={"material_code": 99999999999}, headers=keeper_headers
    )
    assert huge.status_code == 422


def test_get_by_id(client, control, keeper_headers):
    created = client.post("/storage-units", json=receipt(), headers=keeper_headers).json()
    found = client.get(f"/storage-units/{created['id']}", headers=keeper_headers)
    assert found.status_code == 200
    assert found.json() == created
    assert client.get("/storage-units/999999", headers=keeper_headers).status_code == 404


def test_storekeeper_cannot_edit_or_delete(client, control, keeper_headers):
    created = client.post("/storage-units", json=receipt(), headers=keeper_headers).json()
    url = f"/storage-units/{created['id']}"
    assert client.put(url, json=receipt(quantity="1"), headers=keeper_headers).status_code == 403
    assert client.delete(url, headers=keeper_headers).status_code == 403


def test_admin_corrects_and_deletes(client, control, keeper_headers, admin_headers):
    created = client.post("/storage-units", json=receipt(), headers=keeper_headers).json()
    url = f"/storage-units/{created['id']}"

    fixed = client.put(url, json=receipt(quantity="120", unit_price="200"), headers=admin_headers)
    assert fixed.status_code == 200
    assert fixed.json()["cost"] == "24000.00"

    assert (
        client.put("/storage-units/999999", json=receipt(), headers=admin_headers).status_code
        == 404
    )
    assert client.delete(url, headers=admin_headers).status_code == 204
    assert client.get(url, headers=admin_headers).status_code == 404
    assert client.delete(url, headers=admin_headers).status_code == 404


def test_admin_edit_cannot_create_duplicate_order(client, control, keeper_headers, admin_headers):
    created = client.post("/storage-units", json=receipt(), headers=keeper_headers).json()
    clash = receipt(
        order_number="1",
        order_date="2026-12-01",
        supplier_code=101,
        material_code=1001,
        unit_code=166,
    )
    response = client.put(f"/storage-units/{created['id']}", json=clash, headers=admin_headers)
    assert response.status_code == 409


def test_admin_edit_keeps_own_order_number(client, control, keeper_headers, admin_headers):
    created = client.post("/storage-units", json=receipt(), headers=keeper_headers).json()
    response = client.put(
        f"/storage-units/{created['id']}", json=receipt(doc_number="Н-5/1"), headers=admin_headers
    )
    assert response.status_code == 200
    assert response.json()["doc_number"] == "Н-5/1"


def test_admin_can_add_receipt_too(client, control, admin_headers):
    assert client.post("/storage-units", json=receipt(), headers=admin_headers).status_code == 201
