import logging
from datetime import date
from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app import validators
from app.common import PaginationParams, paginate
from app.deps import AdminUser, CurrentUser, DbSession
from app.errors import FieldErrors
from app.models import Document, Material, MaterialUnit, StorageUnit, Supplier, Unit
from app.schemas import Page, StorageUnitIn, StorageUnitOut

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/storage-units", tags=["Учет поступлений"])

UnitId = Annotated[int, Path(ge=1, le=9_223_372_036_854_775_807, description="Идентификатор ЕХ")]
CodeFilter = Annotated[int | None, Query(ge=1, le=validators.MAX_INT)]
DUPLICATE_ORDER = "Единица хранения с таким номером ордера и датой уже существует"


def _check_references(session, data: StorageUnitIn) -> None:
    errors: list[tuple[str, str]] = []
    if session.get(Supplier, data.supplier_code) is None:
        errors.append(("supplier_code", "Поставщик с таким кодом не найден"))
    if session.get(Document, data.doc_code) is None:
        errors.append(("doc_code", "Сопроводительный документ с таким кодом не найден"))
    material_found = session.get(Material, data.material_code) is not None
    if not material_found:
        errors.append(("material_code", "Материал с таким кодом не найден"))
    unit_found = session.get(Unit, data.unit_code) is not None
    if not unit_found:
        errors.append(("unit_code", "Единица измерения с таким кодом не найдена"))
    if (
        material_found
        and unit_found
        and session.get(MaterialUnit, (data.material_code, data.unit_code)) is None
    ):
        errors.append(("unit_code", "Единица измерения недопустима для данного материала"))
    if errors:
        raise FieldErrors(errors)


def _order_exists(session, number: str, order_date: date, exclude_id: int | None = None) -> bool:
    stmt = select(StorageUnit.id).where(
        StorageUnit.order_number == number, StorageUnit.order_date == order_date
    )
    if exclude_id is not None:
        stmt = stmt.where(StorageUnit.id != exclude_id)
    return session.scalar(stmt.limit(1)) is not None


def _commit(session, data: StorageUnitIn, exclude_id: int | None = None) -> None:
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        if _order_exists(session, data.order_number, data.order_date, exclude_id):
            raise HTTPException(409, DUPLICATE_ORDER) from None
        raise HTTPException(409, "Данные конфликтуют с текущим состоянием справочников") from None


@router.post(
    "",
    response_model=StorageUnitOut,
    status_code=201,
    summary="Ф2. Добавление единицы хранения",
    responses={409: {"description": DUPLICATE_ORDER}},
)
def create_storage_unit(payload: StorageUnitIn, session: DbSession, user: CurrentUser):
    _check_references(session, payload)
    if _order_exists(session, payload.order_number, payload.order_date):
        raise HTTPException(409, DUPLICATE_ORDER)
    unit = StorageUnit(**payload.model_dump())
    session.add(unit)
    _commit(session, payload)
    logger.info(
        "Добавлена ЕХ id=%s, ордер %s от %s, пользователь=%s",
        unit.id,
        unit.order_number,
        unit.order_date.isoformat(),
        user.login,
    )
    return unit


@router.get(
    "",
    response_model=Page[StorageUnitOut],
    summary="Просмотр единиц хранения (постранично, новые первыми)",
)
def list_storage_units(
    session: DbSession,
    _user: CurrentUser,
    pagination: PaginationParams,
    material_code: CodeFilter = None,
    supplier_code: CodeFilter = None,
):
    stmt = select(StorageUnit)
    if material_code is not None:
        stmt = stmt.where(StorageUnit.material_code == material_code)
    if supplier_code is not None:
        stmt = stmt.where(StorageUnit.supplier_code == supplier_code)
    rows, total = paginate(session, stmt, [StorageUnit.id.desc()], pagination)
    return Page[StorageUnitOut](
        items=[StorageUnitOut.model_validate(row) for row in rows],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.get("/{unit_id}", response_model=StorageUnitOut, summary="Единица хранения по id")
def get_storage_unit(unit_id: UnitId, session: DbSession, _user: CurrentUser):
    unit = session.get(StorageUnit, unit_id)
    if unit is None:
        raise HTTPException(404, "Единица хранения не найдена")
    return unit


@router.put(
    "/{unit_id}",
    response_model=StorageUnitOut,
    summary="Исправление единицы хранения (администратор)",
)
def update_storage_unit(
    unit_id: UnitId, payload: StorageUnitIn, session: DbSession, admin: AdminUser
):
    unit = session.get(StorageUnit, unit_id)
    if unit is None:
        raise HTTPException(404, "Единица хранения не найдена")
    _check_references(session, payload)
    if _order_exists(session, payload.order_number, payload.order_date, exclude_id=unit.id):
        raise HTTPException(409, DUPLICATE_ORDER)
    for field, value in payload.model_dump().items():
        setattr(unit, field, value)
    _commit(session, payload, exclude_id=unit.id)
    logger.info("Исправлена ЕХ id=%s, пользователь=%s", unit.id, admin.login)
    return unit


@router.delete("/{unit_id}", status_code=204, summary="Удаление единицы хранения (администратор)")
def delete_storage_unit(unit_id: UnitId, session: DbSession, admin: AdminUser) -> Response:
    unit = session.get(StorageUnit, unit_id)
    if unit is None:
        raise HTTPException(404, "Единица хранения не найдена")
    session.delete(unit)
    session.commit()
    logger.info("Удалена ЕХ id=%s, пользователь=%s", unit_id, admin.login)
    return Response(status_code=204)
