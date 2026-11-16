from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Annotated, Generic, Literal, TypeVar

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
)

from app import validators

T = TypeVar("T")


def _text(max_length: int):
    return Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=max_length),
        AfterValidator(validators.collapse_spaces),
    ]


Str10 = _text(10)
Str20 = _text(20)
Str30 = _text(30)
Str50 = _text(50)
Str100 = _text(100)
Str150 = _text(150)
Str255 = _text(255)

Code = Annotated[int, Field(ge=1, le=validators.MAX_INT)]


def _check_account(value: str) -> str:
    value = value.strip()
    if not validators.ACCOUNT_RE.fullmatch(value):
        raise ValueError("Ожидается формат «nn» или «nn.nn»")
    return value


def _check_zip(value: str) -> str:
    value = value.strip()
    if not validators.ZIP_RE.fullmatch(value):
        raise ValueError("Почтовый индекс должен состоять из 6 цифр")
    return value


def _check_inn(value: str) -> str:
    value = value.strip()
    if not validators.inn_is_valid(value):
        raise ValueError("ИНН должен содержать 10 или 12 цифр с верной контрольной суммой")
    return value


def _check_bank_account(value: str) -> str:
    value = value.strip()
    if not validators.BANK_ACCOUNT_RE.fullmatch(value):
        raise ValueError("Номер банковского счета должен состоять из 20 цифр")
    return value


def _quantize(places: str):
    exp = Decimal(places)

    def apply(value: Decimal) -> Decimal:
        return value.quantize(exp, rounding=ROUND_HALF_UP)

    return apply


def _check_password(value: str) -> str:
    if len(value.encode()) > 72:
        raise ValueError("Пароль не должен быть длиннее 72 байт")
    return value


Account = Annotated[str, AfterValidator(_check_account)]
ZipCode = Annotated[str, AfterValidator(_check_zip)]
Inn = Annotated[str, AfterValidator(_check_inn)]
BankAccount = Annotated[str, AfterValidator(_check_bank_account)]
Quantity = Annotated[
    Decimal,
    Field(gt=0, max_digits=14, decimal_places=3),
    AfterValidator(_quantize("0.001")),
]
UnitPrice = Annotated[
    Decimal,
    Field(ge=0, max_digits=14, decimal_places=2),
    AfterValidator(_quantize("0.01")),
]
Password = Annotated[str, Field(min_length=8, max_length=72), AfterValidator(_check_password)]
Login = Annotated[str, Field(pattern=r"^[A-Za-z0-9_.-]{3,50}$")]
Role = Literal["storekeeper", "admin"]


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Page(BaseModel, Generic[T]):

    items: list[T]
    total: int
    page: int
    page_size: int

class MaterialBase(BaseModel):
    class_code: Str10
    group_code: Str10
    name: Str255


class MaterialCreate(MaterialBase):
    material_code: Code | None = Field(
        None, description="Если не задан — назначается автоматически"
    )


class MaterialOut(ORMModel):
    material_code: int
    class_code: str
    group_code: str
    name: str


class UnitBase(BaseModel):
    name: Str50
    short_name: Str10


class UnitCreate(UnitBase):
    unit_code: Code | None = Field(None, description="Код по ОКЕИ; если не задан — назначается")


class UnitOut(ORMModel):
    unit_code: int
    name: str
    short_name: str


class DocumentBase(BaseModel):
    name: Str100


class DocumentCreate(DocumentBase):
    doc_code: Code | None = Field(None, description="Если не задан — назначается автоматически")


class DocumentOut(ORMModel):
    doc_code: int
    name: str


class SupplierBase(BaseModel):
    name: Str255
    inn: Inn
    legal_zip: ZipCode
    legal_city: Str100
    legal_street: Str150
    legal_house: Str20
    bank_zip: ZipCode
    bank_city: Str100
    bank_street: Str150
    bank_house: Str20
    bank_account: BankAccount


class SupplierCreate(SupplierBase):
    supplier_code: Code | None = Field(
        None, description="Если не задан — назначается автоматически"
    )


class SupplierOut(ORMModel):
    supplier_code: int
    name: str
    inn: str
    legal_zip: str
    legal_city: str
    legal_street: str
    legal_house: str
    bank_zip: str
    bank_city: str
    bank_street: str
    bank_house: str
    bank_account: str


class MaterialUnitIn(BaseModel):
    unit_code: Code


class MaterialUnitsReplace(BaseModel):
    unit_codes: list[Code] = Field(max_length=100)


class StorageUnitBase(BaseModel):

    order_number: Str20
    order_date: date
    supplier_code: Code
    balance_account: Account
    doc_code: Code
    doc_number: Str30
    material_code: Code
    material_account: Account
    unit_code: Code
    quantity: Quantity
    unit_price: UnitPrice


class StorageUnitIn(StorageUnitBase):

    @field_validator("order_date")
    @classmethod
    def _not_in_future(cls, value: date) -> date:
        if value > validators.today():
            raise ValueError("Дата ордера не может быть позже текущей даты")
        return value


class StorageUnitOut(ORMModel):
    id: int
    order_number: str
    order_date: date
    supplier_code: int
    balance_account: str
    doc_code: int
    doc_number: str
    material_code: int
    material_account: str
    unit_code: int
    quantity: Decimal
    unit_price: Decimal
    cost: Decimal = Field(description="Стоимость: количество × цена, с точностью до копеек")


class MaterialSuppliersCount(BaseModel):
    material_code: int
    material_name: str
    suppliers_count: int


class SuppliersCount(BaseModel):
    suppliers_count: int


class BankAddressQuery(BaseModel):

    zip: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=10),
        AfterValidator(validators.collapse_spaces),
    ]
    city: Str100
    street: Str150
    house: Str20


class LoginIn(BaseModel):
    login: Annotated[str, Field(min_length=1, max_length=50)]
    password: Annotated[str, Field(min_length=1, max_length=256)]


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Срок действия токена, секунд")
    role: str


class UserCreate(BaseModel):
    login: Login
    password: Password
    role: Role
    is_active: bool = True


class UserUpdate(BaseModel):
    role: Role | None = None
    is_active: bool | None = None
    password: Password | None = None


class UserOut(ORMModel):
    id: int
    login: str
    role: str
    is_active: bool
