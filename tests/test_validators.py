from datetime import date

import pytest

from app import validators
from app.config import get_settings


@pytest.mark.parametrize(
    "inn",
    [
        "7707123458",  # поставщики контрольного примера
        "5047112238",
        "7728345613",
        "7707083893",
        "500100732259",  # 12 цифр (ИП)
    ],
)
def test_valid_inn(inn):
    assert validators.inn_is_valid(inn)


@pytest.mark.parametrize(
    "inn",
    [
        "7707123459",  # неверная контрольная цифра (10)
        "500100732258",  # неверная контрольная цифра (12)
        "500100732269",
        "",
        "12345",
        "77071234581",  # 11 цифр
        "abcdefghij",
        "770712345А",
        "٧٧٠٧١٢٣٤٥٨",  # не ASCII-цифры
    ],
)
def test_invalid_inn(inn):
    assert not validators.inn_is_valid(inn)


def test_generated_inn_passes_checksum():
    for i in range(200):
        assert validators.inn_is_valid(validators.make_inn10(str(770_000_000 + i)))


@pytest.mark.parametrize("value", ["10", "60.01", "00.99"])
def test_account_format_accepts(value):
    assert validators.ACCOUNT_RE.fullmatch(value)


@pytest.mark.parametrize("value", ["", "1", "100", "60.1", "60.001", "60,01", "a0.01", " 60.01"])
def test_account_format_rejects(value):
    assert not validators.ACCOUNT_RE.fullmatch(value)


def test_collapse_spaces():
    assert validators.collapse_spaces("  ул.   Банковская \t 5 ") == "ул. Банковская 5"


def test_today_uses_configured_timezone(monkeypatch):
    monkeypatch.undo()
    assert isinstance(validators.today(), date)


def test_settings_defaults():
    settings = get_settings()
    assert settings.access_token_minutes == 60
    assert settings.login_max_attempts == 5
    assert settings.login_lock_minutes == 15
