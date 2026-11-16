from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app import validators
from app.schemas import BankAddressQuery, StorageUnitIn, SupplierBase, UserCreate

VALID = {
    "order_number": " 5 ",
    "order_date": "2026-12-10",
    "supplier_code": 103,
    "balance_account": "60.01",
    "doc_code": 1,
    "doc_number": "Н-5",
    "material_code": 1002,
    "material_account": "10",
    "unit_code": 6,
    "quantity": "100",
    "unit_price": 250,
}


@pytest.fixture(autouse=True)
def fixed_today(monkeypatch):
    monkeypatch.setattr(validators, "today", lambda: date(2026, 12, 22))


def failing_fields(**overrides):
    with pytest.raises(ValidationError) as info:
        StorageUnitIn(**{**VALID, **overrides})
    return {error["loc"][0] for error in info.value.errors()}


def test_valid_receipt_is_normalized():
    unit = StorageUnitIn(**VALID)
    assert unit.order_number == "5"
    assert unit.quantity == Decimal("100.000")
    assert str(unit.quantity) == "100.000"
    assert str(unit.unit_price) == "250.00"


def test_reports_every_failing_field():
    fields = failing_fields(quantity="0", unit_price="-1", balance_account="x", order_number="")
    assert fields == {"quantity", "unit_price", "balance_account", "order_number"}


def test_future_date_is_rejected_but_today_is_fine():
    assert failing_fields(order_date="2026-12-23") == {"order_date"}
    assert StorageUnitIn(**{**VALID, "order_date": "2026-12-22"}).order_date == date(2026, 12, 22)


def test_decimal_precision_limits():
    assert failing_fields(quantity="1.0001") == {"quantity"}
    assert failing_fields(unit_price="1.001") == {"unit_price"}
    assert failing_fields(quantity="1" + "0" * 11) == {
        "quantity"
    }


def test_code_bounds():
    assert failing_fields(supplier_code=0) == {"supplier_code"}
    assert failing_fields(unit_code=2_147_483_648) == {"unit_code"}


def test_supplier_checks_inn_and_account():
    base = {
        "name": "ООО Тест",
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
    assert SupplierBase(**base).inn == "7707083893"
    with pytest.raises(ValidationError):
        SupplierBase(**{**base, "inn": "7707083894"})
    with pytest.raises(ValidationError):
        SupplierBase(**{**base, "bank_account": "1234"})


def test_bank_address_query_normalizes_text():
    query = BankAddressQuery(zip=" 101000", city=" Москва ", street="ул.  Банковская", house="5")
    assert (query.zip, query.city, query.street, query.house) == (
        "101000",
        "Москва",
        "ул. Банковская",
        "5",
    )
    with pytest.raises(ValidationError):
        BankAddressQuery(zip="101000", city="  ", street="ул. Банковская", house="5")


def test_user_password_rules():
    assert UserCreate(login="ivanov", password="12345678", role="admin").is_active is True
    with pytest.raises(ValidationError):
        UserCreate(login="ivanov", password="1234567", role="admin")
    with pytest.raises(ValidationError):
        UserCreate(login="ив", password="12345678", role="admin")
