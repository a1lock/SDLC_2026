import re
from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.config import get_settings

MAX_INT = 2_147_483_647

ACCOUNT_RE = re.compile(r"\d{2}(\.\d{2})?")
ZIP_RE = re.compile(r"\d{6}")
BANK_ACCOUNT_RE = re.compile(r"\d{20}")

_INN10_WEIGHTS = (2, 4, 10, 3, 5, 9, 4, 6, 8)
_INN12_WEIGHTS_1 = (7, 2, 4, 10, 3, 5, 9, 4, 6, 8)
_INN12_WEIGHTS_2 = (3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8)


def today() -> date:
    return datetime.now(ZoneInfo(get_settings().timezone)).date()


def collapse_spaces(value: str) -> str:
    return " ".join(value.split())


def _check_digit(digits: list[int], weights: tuple[int, ...]) -> int:
    return sum(w * d for w, d in zip(weights, digits, strict=True)) % 11 % 10


def inn_is_valid(inn: str) -> bool:
    if not (inn.isascii() and inn.isdigit()):
        return False
    digits = [int(c) for c in inn]
    if len(digits) == 10:
        return _check_digit(digits[:9], _INN10_WEIGHTS) == digits[9]
    if len(digits) == 12:
        return (
            _check_digit(digits[:10], _INN12_WEIGHTS_1) == digits[10]
            and _check_digit(digits[:11], _INN12_WEIGHTS_2) == digits[11]
        )
    return False


def make_inn10(first_nine: str) -> str:
    digits = [int(c) for c in first_nine]
    return first_nine + str(_check_digit(digits, _INN10_WEIGHTS))
