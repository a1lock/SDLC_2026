import hashlib
from typing import Annotated, NamedTuple

from fastapi import Depends, Query, Request, Response
from pydantic import BaseModel
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

CACHE_CONTROL = "private, no-cache"


class Pagination(NamedTuple):
    page: int
    page_size: int

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


def pagination_params(
    page: Annotated[int, Query(ge=1, le=1_000_000, description="Номер страницы")] = 1,
    page_size: Annotated[int, Query(ge=1, le=500, description="Размер страницы")] = 50,
) -> Pagination:
    return Pagination(page, page_size)


PaginationParams = Annotated[Pagination, Depends(pagination_params)]


def paginate(session: Session, stmt: Select, order_by: list, pagination: Pagination):
    total = session.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
    rows = session.scalars(
        stmt.order_by(*order_by).limit(pagination.page_size).offset(pagination.offset)
    ).all()
    return rows, total or 0


def _etag_matches(header: str | None, etag: str) -> bool:
    if not header:
        return False
    candidates = [part.strip() for part in header.split(",")]
    return "*" in candidates or any(c.removeprefix("W/") == etag for c in candidates)


def cached_json(request: Request, payload: BaseModel) -> Response:
    return cached_body(request, payload.model_dump_json().encode())


def cached_body(request: Request, body: bytes) -> Response:
    etag = f'"{hashlib.sha256(body).hexdigest()[:32]}"'
    headers = {"ETag": etag, "Cache-Control": CACHE_CONTROL}
    if _etag_matches(request.headers.get("if-none-match"), etag):
        return Response(status_code=304, headers=headers)
    return Response(content=body, media_type="application/json", headers=headers)
