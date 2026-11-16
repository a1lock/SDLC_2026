import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import InterfaceError, OperationalError
from sqlalchemy.exc import TimeoutError as PoolTimeoutError

logger = logging.getLogger(__name__)

DB_UNAVAILABLE_MESSAGE = "База данных недоступна. Повторите запрос позже."


class FieldErrors(Exception):

    def __init__(self, errors: list[tuple[str, str]], where: str = "body") -> None:
        super().__init__("; ".join(f"{field}: {message}" for field, message in errors))
        self.errors = errors
        self.where = where


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(FieldErrors)
    async def field_errors_handler(request: Request, exc: FieldErrors) -> JSONResponse:
        detail = [
            {"loc": [exc.where, field], "msg": message, "type": "value_error.reference"}
            for field, message in exc.errors
        ]
        return JSONResponse(status_code=422, content={"detail": detail})

    async def db_unavailable_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error("База данных недоступна (%s): %s", type(exc).__name__, request.url.path)
        return JSONResponse(status_code=503, content={"detail": DB_UNAVAILABLE_MESSAGE})

    for exception_class in (OperationalError, InterfaceError, PoolTimeoutError):
        app.add_exception_handler(exception_class, db_unavailable_handler)
