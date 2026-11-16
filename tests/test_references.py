import pytest

from tests.conftest import error_fields

MATERIAL = {"class_code": "10", "group_code": "02", "name": "Труба стальная"}
SUPPLIER = {
    "name": "ООО «Тест»",
    "inn": "7707083893",
    "legal_zip": "125009",
    "legal_city": "Москва",
    "legal_street": "ул. Тверская",
    "legal_house": "1",
    "bank_zip": "101000",
    "bank_city": "Москва",
    "bank_street": "ул. Банковская",
    "bank_house": "5",
    "bank_account": "40702810100000000999",
}


def test_codes_are_assigned_automatically_or_taken_from_request(client, admin_headers):
    first = client.post("/materials", json=MATERIAL, headers=admin_headers)
    assert first.status_code == 201
    assert first.json()["material_code"] == 1
    explicit = client.post(
        "/materials", json={**MATERIAL, "material_code": 1001}, headers=admin_headers
    )
    assert explicit.json()["material_code"] == 1001
    again = client.post(
        "/materials", json={**MATERIAL, "material_code": 1001}, headers=admin_headers
    )
    assert again.status_code == 409
    after = client.post("/materials", json=MATERIAL, headers=admin_headers)
    assert after.json()["material_code"] == 1002


def test_storekeeper_reads_but_cannot_change(client, control, keeper_headers):
    assert client.get("/materials", headers=keeper_headers).status_code == 200
    assert (
        client.get("/materials/1001", headers=keeper_headers).json()["name"] == "Лист стальной 3 мм"
    )
    assert client.post("/materials", json=MATERIAL, headers=keeper_headers).status_code == 403
    assert client.put("/materials/1001", json=MATERIAL, headers=keeper_headers).status_code == 403
    assert client.delete("/materials/1003", headers=keeper_headers).status_code == 403


def test_list_search_and_pagination(client, control, keeper_headers):
    everything = client.get("/materials", headers=keeper_headers).json()
    assert everything["total"] == 3
    assert [m["material_code"] for m in everything["items"]] == [1001, 1002, 1003]

    found = client.get("/materials", params={"q": "КАБЕЛЬ"}, headers=keeper_headers).json()
    assert [m["material_code"] for m in found["items"]] == [1002]

    page = client.get(
        "/materials", params={"page": 2, "page_size": 2}, headers=keeper_headers
    ).json()
    assert page["total"] == 3
    assert [m["material_code"] for m in page["items"]] == [1003]


@pytest.mark.parametrize("params", [{"page": 0}, {"page_size": 0}, {"page_size": 501}])
def test_bad_pagination_is_rejected(client, keeper_headers, params):
    assert client.get("/materials", params=params, headers=keeper_headers).status_code == 422


def test_etag_gives_304_until_data_changes(client, control, admin_headers):
    first = client.get("/units", headers=admin_headers)
    etag = first.headers["ETag"]
    assert first.status_code == 200

    cached = client.get("/units", headers={**admin_headers, "If-None-Match": etag})
    assert cached.status_code == 304
    assert cached.content == b""

    client.post("/units", json={"name": "пачка", "short_name": "пач"}, headers=admin_headers)
    changed = client.get("/units", headers={**admin_headers, "If-None-Match": etag})
    assert changed.status_code == 200
    assert changed.headers["ETag"] != etag


def test_single_record_supports_etag(client, control, keeper_headers):
    first = client.get("/documents/1", headers=keeper_headers)
    cached = client.get(
        "/documents/1", headers={**keeper_headers, "If-None-Match": first.headers["ETag"]}
    )
    assert cached.status_code == 304


def test_update_and_missing_records(client, control, admin_headers):
    changed = client.put(
        "/materials/1003", json={**MATERIAL, "name": "Масло ТКп"}, headers=admin_headers
    )
    assert changed.status_code == 200
    assert changed.json()["name"] == "Масло ТКп"
    assert client.put("/materials/777", json=MATERIAL, headers=admin_headers).status_code == 404
    assert client.get("/materials/777", headers=admin_headers).status_code == 404
    assert client.delete("/materials/777", headers=admin_headers).status_code == 404


def test_unreferenced_record_can_be_deleted(client, admin_headers):
    client.post("/documents", json={"name": "Акт"}, headers=admin_headers)
    assert client.delete("/documents/1", headers=admin_headers).status_code == 204
    assert client.get("/documents/1", headers=admin_headers).status_code == 404


@pytest.mark.parametrize(
    "url", ["/materials/1001", "/suppliers/101", "/documents/1", "/units/166", "/units/6"]
)
def test_referenced_record_cannot_be_deleted(client, control, admin_headers, url):
    assert client.delete(url, headers=admin_headers).status_code == 409
    assert client.get(url, headers=admin_headers).status_code == 200


def test_unique_names_conflict(client, control, admin_headers):
    assert (
        client.post(
            "/units", json={"name": "метр", "short_name": "м."}, headers=admin_headers
        ).status_code
        == 409
    )
    assert (
        client.post("/documents", json={"name": "Накладная"}, headers=admin_headers).status_code
        == 409
    )


def test_supplier_is_created_with_normalized_text(client, admin_headers):
    payload = {**SUPPLIER, "name": "  ООО   «Тест»  ", "bank_city": "  Санкт-Петербург "}
    response = client.post("/suppliers", json=payload, headers=admin_headers)
    assert response.status_code == 201
    assert response.json()["name"] == "ООО «Тест»"
    assert response.json()["bank_city"] == "Санкт-Петербург"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("inn", "7707083894"),
        ("inn", "12345"),
        ("legal_zip", "12"),
        ("bank_account", "123"),
        ("name", "   "),
    ],
)
def test_supplier_validation(client, admin_headers, field, value):
    response = client.post("/suppliers", json={**SUPPLIER, field: value}, headers=admin_headers)
    assert response.status_code == 422
    assert field in error_fields(response)


def test_supplier_inn_is_unique(client, admin_headers):
    assert client.post("/suppliers", json=SUPPLIER, headers=admin_headers).status_code == 201
    again = client.post("/suppliers", json=SUPPLIER, headers=admin_headers)
    assert again.status_code == 409


def test_huge_code_in_path_is_rejected(client, keeper_headers):
    assert client.get("/materials/99999999999", headers=keeper_headers).status_code == 422


def test_material_units_read(client, control, keeper_headers):
    response = client.get("/materials/1001/units", headers=keeper_headers)
    assert response.status_code == 200
    assert [u["unit_code"] for u in response.json()] == [166]
    assert client.get("/materials/9999/units", headers=keeper_headers).status_code == 404
    cached = client.get(
        "/materials/1001/units",
        headers={**keeper_headers, "If-None-Match": response.headers["ETag"]},
    )
    assert cached.status_code == 304


def test_material_units_add_and_remove(client, control, admin_headers):
    added = client.post("/materials/1003/units", json={"unit_code": 113}, headers=admin_headers)
    assert added.status_code == 201
    assert added.json()["short_name"] == "м3"
    assert (
        client.post(
            "/materials/1003/units", json={"unit_code": 113}, headers=admin_headers
        ).status_code
        == 409
    )
    unknown = client.post("/materials/1003/units", json={"unit_code": 4242}, headers=admin_headers)
    assert unknown.status_code == 422
    assert "unit_code" in error_fields(unknown)
    assert client.delete("/materials/1003/units/113", headers=admin_headers).status_code == 204
    assert client.delete("/materials/1003/units/113", headers=admin_headers).status_code == 404


def test_material_units_replace(client, control, admin_headers):
    replaced = client.put(
        "/materials/1003/units", json={"unit_codes": [112, 113]}, headers=admin_headers
    )
    assert replaced.status_code == 200
    assert [u["unit_code"] for u in replaced.json()] == [112, 113]
    unknown = client.put(
        "/materials/1003/units", json={"unit_codes": [4242]}, headers=admin_headers
    )
    assert unknown.status_code == 422


def test_unit_used_in_receipts_cannot_be_removed(client, control, admin_headers):
    assert client.delete("/materials/1001/units/166", headers=admin_headers).status_code == 409
    replace = client.put("/materials/1001/units", json={"unit_codes": []}, headers=admin_headers)
    assert replace.status_code == 409
    still = client.get("/materials/1001/units", headers=admin_headers)
    assert [u["unit_code"] for u in still.json()] == [166]


def test_storekeeper_cannot_change_material_units(client, control, keeper_headers):
    assert (
        client.post(
            "/materials/1003/units", json={"unit_code": 113}, headers=keeper_headers
        ).status_code
        == 403
    )
    assert (
        client.put(
            "/materials/1003/units", json={"unit_codes": []}, headers=keeper_headers
        ).status_code
        == 403
    )
    assert client.delete("/materials/1003/units/112", headers=keeper_headers).status_code == 403
