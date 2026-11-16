from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query
from sqlalchemy import func, select

from app import validators
from app.deps import CurrentUser, DbSession
from app.models import Material, StorageUnit, Supplier
from app.schemas import BankAddressQuery, MaterialSuppliersCount, SupplierOut, SuppliersCount

router = APIRouter(tags=["Справки"])

MaterialCode = Annotated[int, Path(ge=1, le=validators.MAX_INT, description="Код материала")]
MATERIAL_NOT_FOUND = "Материал не найден"


def _require_material(session, code: int) -> Material:
    material = session.get(Material, code)
    if material is None:
        raise HTTPException(404, MATERIAL_NOT_FOUND)
    return material


@router.get(
    "/materials/{code}/suppliers/count",
    response_model=MaterialSuppliersCount,
    summary="Ф1. Число поставщиков материала",
)
def count_material_suppliers(code: MaterialCode, session: DbSession, _user: CurrentUser):
    material = _require_material(session, code)
    count = session.scalar(
        select(func.count(StorageUnit.supplier_code.distinct())).where(
            StorageUnit.material_code == code
        )
    )
    return MaterialSuppliersCount(
        material_code=material.material_code,
        material_name=material.name,
        suppliers_count=count or 0,
    )


@router.get(
    "/materials/{code}/suppliers",
    response_model=list[SupplierOut],
    summary="Ф3. Список поставщиков материала",
)
def list_material_suppliers(code: MaterialCode, session: DbSession, _user: CurrentUser):
    _require_material(session, code)
    supplier_codes = (
        select(StorageUnit.supplier_code).where(StorageUnit.material_code == code).distinct()
    )
    stmt = (
        select(Supplier)
        .where(Supplier.supplier_code.in_(supplier_codes))
        .order_by(Supplier.name, Supplier.supplier_code)
    )
    return session.scalars(stmt).all()


@router.get(
    "/banks/suppliers/count",
    response_model=SuppliersCount,
    summary="Ф4. Число поставщиков банка по адресу",
)
def count_bank_suppliers(
    address: Annotated[BankAddressQuery, Query()], session: DbSession, _user: CurrentUser
):
    stmt = (
        select(func.count())
        .select_from(Supplier)
        .where(
            func.lower(Supplier.bank_zip) == func.lower(address.zip),
            func.lower(Supplier.bank_city) == func.lower(address.city),
            func.lower(Supplier.bank_street) == func.lower(address.street),
            func.lower(Supplier.bank_house) == func.lower(address.house),
        )
    )
    return SuppliersCount(suppliers_count=session.scalar(stmt) or 0)
