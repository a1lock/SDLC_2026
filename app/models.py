from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
    true,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

ROLE_STOREKEEPER = "storekeeper"
ROLE_ADMIN = "admin"
ROLES = (ROLE_STOREKEEPER, ROLE_ADMIN)

BigIntPK = BigInteger().with_variant(Integer(), "sqlite")


class Base(DeclarativeBase):
    pass


class Supplier(Base):

    __tablename__ = "suppliers"

    supplier_code: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    inn: Mapped[str] = mapped_column(String(12), unique=True, nullable=False)
    legal_zip: Mapped[str] = mapped_column(String(10), nullable=False)
    legal_city: Mapped[str] = mapped_column(String(100), nullable=False)
    legal_street: Mapped[str] = mapped_column(String(150), nullable=False)
    legal_house: Mapped[str] = mapped_column(String(20), nullable=False)
    bank_zip: Mapped[str] = mapped_column(String(10), nullable=False)
    bank_city: Mapped[str] = mapped_column(String(100), nullable=False)
    bank_street: Mapped[str] = mapped_column(String(150), nullable=False)
    bank_house: Mapped[str] = mapped_column(String(20), nullable=False)
    bank_account: Mapped[str] = mapped_column(String(20), nullable=False)


class Material(Base):
    __tablename__ = "materials"

    material_code: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    class_code: Mapped[str] = mapped_column(String(10), nullable=False)
    group_code: Mapped[str] = mapped_column(String(10), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)


class Unit(Base):

    __tablename__ = "units"

    unit_code: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    short_name: Mapped[str] = mapped_column(String(10), nullable=False)


class MaterialUnit(Base):

    __tablename__ = "material_units"

    material_code: Mapped[int] = mapped_column(
        ForeignKey("materials.material_code"), primary_key=True
    )
    unit_code: Mapped[int] = mapped_column(ForeignKey("units.unit_code"), primary_key=True)


class Document(Base):

    __tablename__ = "documents"

    doc_code: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)


class StorageUnit(Base):

    __tablename__ = "storage_units"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    order_number: Mapped[str] = mapped_column(String(20), nullable=False)
    order_date: Mapped[date] = mapped_column(Date, nullable=False)
    supplier_code: Mapped[int] = mapped_column(
        ForeignKey("suppliers.supplier_code"), nullable=False
    )
    balance_account: Mapped[str] = mapped_column(String(20), nullable=False)
    doc_code: Mapped[int] = mapped_column(ForeignKey("documents.doc_code"), nullable=False)
    doc_number: Mapped[str] = mapped_column(String(30), nullable=False)
    material_code: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_code: Mapped[int] = mapped_column(Integer, nullable=False)
    material_account: Mapped[str] = mapped_column(String(20), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)

    __table_args__ = (
        UniqueConstraint("order_number", "order_date", name="uq_storage_units_order"),
        ForeignKeyConstraint(
            ["material_code", "unit_code"],
            ["material_units.material_code", "material_units.unit_code"],
            name="fk_storage_units_material_unit",
        ),
        CheckConstraint("quantity > 0", name="ck_storage_units_quantity"),
        CheckConstraint("unit_price >= 0", name="ck_storage_units_unit_price"),
        Index("ix_storage_units_material_supplier", "material_code", "supplier_code"),
    )

    @property
    def cost(self) -> Decimal:
        return calc_cost(self.quantity, self.unit_price)


class User(Base):

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    login: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=true()
    )

    __table_args__ = (CheckConstraint("role IN ('storekeeper', 'admin')", name="ck_users_role"),)


def calc_cost(quantity: Decimal, unit_price: Decimal) -> Decimal:
    return (quantity * unit_price).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


_suppliers = Supplier.__table__
Index(
    "ix_suppliers_bank_address",
    _suppliers.c.bank_zip,
    _suppliers.c.bank_city,
    _suppliers.c.bank_street,
    _suppliers.c.bank_house,
)
Index(
    "ix_suppliers_bank_address_lower",
    func.lower(_suppliers.c.bank_zip),
    func.lower(_suppliers.c.bank_city),
    func.lower(_suppliers.c.bank_street),
    func.lower(_suppliers.c.bank_house),
)
