from tests.conftest import error_fields, receipt

BANK_MOSCOW = {"zip": "101000", "city": "Москва", "street": "ул. Банковская", "house": "5"}
BANK_SPB = {"zip": "190000", "city": "Санкт-Петербург", "street": "ул. Финансовая", "house": "12"}
SUPPLIER_FIELDS = {
    "supplier_code",
    "name",
    "inn",
    "legal_zip",
    "legal_city",
    "legal_street",
    "legal_house",
    "bank_zip",
    "bank_city",
    "bank_street",
    "bank_house",
    "bank_account",
}


def total_units(client, headers):
    return client.get("/storage-units", headers=headers).json()["total"]


def test_01_f1_material_1001(client, control, keeper_headers):
    response = client.get("/materials/1001/suppliers/count", headers=keeper_headers)
    assert response.status_code == 200
    assert response.json() == {
        "material_code": 1001,
        "material_name": "Лист стальной 3 мм",
        "suppliers_count": 2,
    }


def test_02_f1_material_without_receipts(client, control, keeper_headers):
    response = client.get("/materials/1003/suppliers/count", headers=keeper_headers)
    assert response.status_code == 200
    assert response.json()["suppliers_count"] == 0


def test_03_f1_unknown_material(client, control, keeper_headers):
    response = client.get("/materials/9999/suppliers/count", headers=keeper_headers)
    assert response.status_code == 404
    assert response.json()["detail"] == "Материал не найден"


def test_04_f3_two_suppliers_sorted_by_name(client, control, keeper_headers):
    response = client.get("/materials/1001/suppliers", headers=keeper_headers)
    assert response.status_code == 200
    suppliers = response.json()
    assert [s["supplier_code"] for s in suppliers] == [102, 101]
    assert all(set(s) == SUPPLIER_FIELDS for s in suppliers)
    assert suppliers[1]["inn"] == "7707123458"
    assert suppliers[1]["bank_city"] == "Москва"


def test_05_f3_material_without_receipts(client, control, keeper_headers):
    response = client.get("/materials/1003/suppliers", headers=keeper_headers)
    assert response.status_code == 200
    assert response.json() == []


def test_06_f4_moscow_bank(client, control, keeper_headers):
    response = client.get("/banks/suppliers/count", params=BANK_MOSCOW, headers=keeper_headers)
    assert response.status_code == 200
    assert response.json() == {"suppliers_count": 2}


def test_07_f4_spb_bank(client, control, keeper_headers):
    response = client.get("/banks/suppliers/count", params=BANK_SPB, headers=keeper_headers)
    assert response.json() == {"suppliers_count": 1}


def test_08_f4_unknown_address(client, control, keeper_headers):
    params = {**BANK_MOSCOW, "street": "ул. Несуществующая"}
    response = client.get("/banks/suppliers/count", params=params, headers=keeper_headers)
    assert response.status_code == 200
    assert response.json() == {"suppliers_count": 0}


def test_09_f2_valid_receipt(client, control, keeper_headers):
    response = client.post("/storage-units", json=receipt(), headers=keeper_headers)
    assert response.status_code == 201
    body = response.json()
    assert body["id"] > 0
    assert body["order_number"] == "5"
    assert body["order_date"] == "2026-12-10"
    assert body["cost"] == "25000.00"
    assert total_units(client, keeper_headers) == 5

    count = client.get("/materials/1002/suppliers/count", headers=keeper_headers)
    assert count.json()["suppliers_count"] == 1

def test_10_f2_negative_quantity(client, control, keeper_headers):
    response = client.post("/storage-units", json=receipt(quantity="-5"), headers=keeper_headers)
    assert response.status_code == 422
    assert "quantity" in error_fields(response)
    assert total_units(client, keeper_headers) == 4


def test_11_f2_unknown_supplier(client, control, keeper_headers):
    response = client.post(
        "/storage-units", json=receipt(supplier_code=999), headers=keeper_headers
    )
    assert response.status_code == 422
    assert "supplier_code" in error_fields(response)
    assert total_units(client, keeper_headers) == 4


def test_12_f2_duplicate_order(client, control, keeper_headers):
    duplicate = receipt(
        order_number="1",
        order_date="2026-12-01",
        supplier_code=101,
        material_code=1001,
        unit_code=166,
    )
    response = client.post("/storage-units", json=duplicate, headers=keeper_headers)
    assert response.status_code == 409
    assert total_units(client, keeper_headers) == 4


def test_13_f2_unit_not_allowed_for_material(client, control, keeper_headers):
    response = client.post(
        "/storage-units", json=receipt(material_code=1001, unit_code=6), headers=keeper_headers
    )
    assert response.status_code == 422
    assert "unit_code" in error_fields(response)
    assert total_units(client, keeper_headers) == 4


def test_14_f6_storekeeper_cannot_change_reference(client, control, keeper_headers):
    payload = {"class_code": "10", "group_code": "01", "name": "Новый материал"}
    response = client.post("/materials", json=payload, headers=keeper_headers)
    assert response.status_code == 403
    response = client.put("/materials/1001", json=payload, headers=keeper_headers)
    assert response.status_code == 403
