import logging
from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Request, Response
from pydantic import TypeAdapter
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app import validators
from app.common import cached_body
from app.deps import AdminUser, CurrentUser, DbSession
from app.errors import FieldErrors
from app.models import Material, MaterialUnit, Unit
from app.schemas import MaterialUnitIn, MaterialUnitsReplace, UnitOut

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/materials/{code}/units", tags=["Справочники"])

CodePath = Annotated[int, Path(ge=1, le=validators.MAX_INT, description="Код материала")]
UnitCodePath = Annotated[int, Path(ge=1, le=validators.MAX_INT, description="Код единицы")]
IN_USE = "Единица измерения используется в единицах хранения и не может быть удалена"
_unit_list = TypeAdapter(list[UnitOut])


def _require_material(session, code: int) -> Material:
    material = session.get(Material, code)
    if material is None:
        raise HTTPException(404, "Материал не найден")
    return material


def _units_of(session, code: int) -> list[Unit]:
    stmt = (
        select(Unit)
        .join(MaterialUnit, MaterialUnit.unit_code == Unit.unit_code)
        .where(MaterialUnit.material_code == code)
        .order_by(Unit.unit_code)
    )
    return list(session.scalars(stmt).all())


@router.get(
    "",
    response_model=list[UnitOut],
    responses={304: {"description": "Данные не изменились (ETag совпал)"}},
    summary="Допустимые единицы измерения материала",
)
def list_material_units(request: Request, code: CodePath, session: DbSession, _user: CurrentUser):
    _require_material(session, code)
    units = [UnitOut.model_validate(unit) for unit in _units_of(session, code)]
    return cached_body(request, _unit_list.dump_json(units))


@router.post(
    "",
    response_model=UnitOut,
    status_code=201,
    summary="Добавить допустимую единицу измерения",
)
def add_material_unit(
    code: CodePath, payload: MaterialUnitIn, session: DbSession, admin: AdminUser
):
    _require_material(session, code)
    unit = session.get(Unit, payload.unit_code)
    if unit is None:
        raise FieldErrors([("unit_code", "Единица измерения с таким кодом не найдена")])
    if session.get(MaterialUnit, (code, payload.unit_code)) is not None:
        raise HTTPException(409, "Эта единица уже допустима для материала")
    session.add(MaterialUnit(material_code=code, unit_code=payload.unit_code))
    session.commit()
    logger.info(
        "Материал %s: добавлена единица %s, пользователь=%s", code, payload.unit_code, admin.login
    )
    return unit


@router.put(
    "",
    response_model=list[UnitOut],
    summary="Заменить набор допустимых единиц измерения",
)
def replace_material_units(
    code: CodePath, payload: MaterialUnitsReplace, session: DbSession, admin: AdminUser
):
    _require_material(session, code)
    wanted = set(payload.unit_codes)
    if wanted:
        found = set(session.scalars(select(Unit.unit_code).where(Unit.unit_code.in_(wanted))).all())
        if found != wanted:
            missing = ", ".join(str(c) for c in sorted(wanted - found))
            raise FieldErrors([("unit_codes", f"Не найдены единицы измерения с кодами: {missing}")])

    current = set(
        session.scalars(
            select(MaterialUnit.unit_code).where(MaterialUnit.material_code == code)
        ).all()
    )
    for unit_code in current - wanted:
        session.delete(session.get(MaterialUnit, (code, unit_code)))
    for unit_code in wanted - current:
        session.add(MaterialUnit(material_code=code, unit_code=unit_code))
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(409, IN_USE) from None
    logger.info("Материал %s: набор единиц заменен, пользователь=%s", code, admin.login)
    return _units_of(session, code)


@router.delete(
    "/{unit_code}",
    status_code=204,
    summary="Убрать единицу измерения из допустимых",
)
def delete_material_unit(
    code: CodePath, unit_code: UnitCodePath, session: DbSession, admin: AdminUser
) -> Response:
    link = session.get(MaterialUnit, (code, unit_code))
    if link is None:
        raise HTTPException(404, "Связь материала с единицей измерения не найдена")
    session.delete(link)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(409, IN_USE) from None
    logger.info("Материал %s: убрана единица %s, пользователь=%s", code, unit_code, admin.login)
    return Response(status_code=204)
