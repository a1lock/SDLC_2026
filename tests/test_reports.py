import pytest

from tests.conftest import error_fields, receipt

BANK = {"zip": "101000", "city": "Москва", "street": "ул. Банковская", "house": "5"}


def test_f4_ignores_case_and_extra_spaces(client, control, keeper_headers):
    params = {"zip": " 101000 ", "city": "  мОСКВА", "street": "УЛ.   банковская", "house": "5 "}
    response = client.get("/banks/suppliers/count", params=params, headers=keeper_headers)
    assert response.status_code == 200
    assert response.json() == {"suppliers_count": 2}


@pytest.mark.parametrize("missing", ["zip", "city", "street", "house"])
def test_f4_requires_every_address_part(client, control, keeper_headers, missing):
    params = {k: v for k, v in BANK.items() if k != missing}
    response = client.get("/banks/suppliers/count", params=params, headers=keeper_headers)
    assert response.status_code == 422
    assert missing in error_fields(response)


@pytest.mark.parametrize("blank", ["", "   "])
def test_f4_rejects_blank_address_part(client, control, keeper_headers, blank):
    response = client.get(
        "/banks/suppliers/count", params={**BANK, "house": blank}, headers=keeper_headers
    )
    assert response.status_code == 422
    assert "house" in error_fields(response)


def test_f4_counts_suppliers_not_receipts(client, control, keeper_headers):
    payload = receipt(order_number="50", supplier_code=101, material_code=1001, unit_code=166)
    assert client.post("/storage-units", json=payload, headers=keeper_headers).status_code == 201
    response = client.get("/banks/suppliers/count", params=BANK, headers=keeper_headers)
    assert response.json() == {"suppliers_count": 2}


def test_f1_and_f3_follow_new_receipts(client, control, keeper_headers):
    payload = receipt(order_number="60", supplier_code=101, material_code=1002, unit_code=6)
    client.post("/storage-units", json=payload, headers=keeper_headers)
    count = client.get("/materials/1002/suppliers/count", headers=keeper_headers)
    assert count.json()["suppliers_count"] == 2
    listing = client.get("/materials/1002/suppliers", headers=keeper_headers).json()
    assert [s["supplier_code"] for s in listing] == [
        101,
        103,
    ]


def test_f3_unknown_material(client, control, keeper_headers):
    response = client.get("/materials/9999/suppliers", headers=keeper_headers)
    assert response.status_code == 404
    assert response.json()["detail"] == "Материал не найден"


def test_reports_require_authentication(client, control):
    assert client.get("/materials/1001/suppliers/count").status_code == 401
    assert client.get("/materials/1001/suppliers").status_code == 401
    assert client.get("/banks/suppliers/count", params=BANK).status_code == 401


def test_huge_material_code_gives_422_not_500(client, control, keeper_headers):
    response = client.get("/materials/99999999999/suppliers/count", headers=keeper_headers)
    assert response.status_code == 422
