import logging
from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query, Request, Response
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError

from app import validators
from app.common import PaginationParams, cached_json, paginate
from app.deps import AdminUser, CurrentUser, DbSession
from app.models import Document, Material, Supplier, Unit
from app.schemas import (
    DocumentBase,
    DocumentCreate,
    DocumentOut,
    MaterialBase,
    MaterialCreate,
    MaterialOut,
    Page,
    SupplierBase,
    SupplierCreate,
    SupplierOut,
    UnitBase,
    UnitCreate,
    UnitOut,
)

logger = logging.getLogger(__name__)

CodePath = Annotated[int, Path(ge=1, le=validators.MAX_INT, description="Код записи")]
NOT_FOUND = "Запись не найдена"
CONFLICT_CREATE = "Запись с таким кодом или уникальным значением уже существует"
CONFLICT_UPDATE = "Нарушено ограничение уникальности значения"
CONFLICT_DELETE = "Запись используется в других данных и не может быть удалена"


def build_reference_router(
    *,
    prefix: str,
    model,
    pk: str,
    create_schema,
    update_schema,
    out_schema,
    search_columns: list,
    title: str,
) -> APIRouter:
    router = APIRouter(prefix=prefix, tags=["Справочники"])
    pk_column = getattr(model, pk)
    page_schema = Page[out_schema]
    not_modified = {304: {"description": "Данные не изменились (ETag совпал)"}}

    @router.get("", response_model=page_schema, responses=not_modified, summary=f"{title}: список")
    def list_items(
        request: Request,
        session: DbSession,
        _user: CurrentUser,
        pagination: PaginationParams,
        q: Annotated[str | None, Query(max_length=100, description="Поиск по тексту")] = None,
    ):
        stmt = select(model)
        if q and q.strip():
            text = q.strip()
            stmt = stmt.where(or_(*[c.icontains(text, autoescape=True) for c in search_columns]))
        rows, total = paginate(session, stmt, [pk_column], pagination)
        page = page_schema(
            items=[out_schema.model_validate(row) for row in rows],
            total=total,
            page=pagination.page,
            page_size=pagination.page_size,
        )
        return cached_json(request, page)

    @router.get(
        "/{code}", response_model=out_schema, responses=not_modified, summary=f"{title}: запись"
    )
    def get_item(request: Request, code: CodePath, session: DbSession, _user: CurrentUser):
        obj = session.get(model, code)
        if obj is None:
            raise HTTPException(404, NOT_FOUND)
        return cached_json(request, out_schema.model_validate(obj))

    @router.post("", response_model=out_schema, status_code=201, summary=f"{title}: добавить")
    def create_item(payload: create_schema, session: DbSession, admin: AdminUser):
        data = payload.model_dump()
        code = data.pop(pk)
        if code is None:
            code = (session.scalar(select(func.max(pk_column))) or 0) + 1
        obj = model(**{pk: code}, **data)
        session.add(obj)
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            raise HTTPException(409, CONFLICT_CREATE) from None
        logger.info(
            "Справочник %s: добавлена запись %s=%s, пользователь=%s", prefix, pk, code, admin.login
        )
        return obj

    @router.put("/{code}", response_model=out_schema, summary=f"{title}: изменить")
    def update_item(code: CodePath, payload: update_schema, session: DbSession, admin: AdminUser):
        obj = session.get(model, code)
        if obj is None:
            raise HTTPException(404, NOT_FOUND)
        for field, value in payload.model_dump().items():
            setattr(obj, field, value)
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            raise HTTPException(409, CONFLICT_UPDATE) from None
        logger.info(
            "Справочник %s: изменена запись %s=%s, пользователь=%s", prefix, pk, code, admin.login
        )
        return obj

    @router.delete("/{code}", status_code=204, summary=f"{title}: удалить (если нет ссылок)")
    def delete_item(code: CodePath, session: DbSession, admin: AdminUser) -> Response:
        obj = session.get(model, code)
        if obj is None:
            raise HTTPException(404, NOT_FOUND)
        session.delete(obj)
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            raise HTTPException(409, CONFLICT_DELETE) from None
        logger.info(
            "Справочник %s: удалена запись %s=%s, пользователь=%s", prefix, pk, code, admin.login
        )
        return Response(status_code=204)

    return router


materials_router = build_reference_router(
    prefix="/materials",
    model=Material,
    pk="material_code",
    create_schema=MaterialCreate,
    update_schema=MaterialBase,
    out_schema=MaterialOut,
    search_columns=[Material.name, Material.class_code, Material.group_code],
    title="Материалы",
)
units_router = build_reference_router(
    prefix="/units",
    model=Unit,
    pk="unit_code",
    create_schema=UnitCreate,
    update_schema=UnitBase,
    out_schema=UnitOut,
    search_columns=[Unit.name, Unit.short_name],
    title="Единицы измерения",
)
suppliers_router = build_reference_router(
    prefix="/suppliers",
    model=Supplier,
    pk="supplier_code",
    create_schema=SupplierCreate,
    update_schema=SupplierBase,
    out_schema=SupplierOut,
    search_columns=[Supplier.name, Supplier.inn],
    title="Поставщики",
)
documents_router = build_reference_router(
    prefix="/documents",
    model=Document,
    pk="doc_code",
    create_schema=DocumentCreate,
    update_schema=DocumentBase,
    out_schema=DocumentOut,
    search_columns=[Document.name],
    title="Документы",
)

reference_routers = [materials_router, units_router, suppliers_router, documents_router]
