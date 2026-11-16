from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.config import get_settings
from app.deps import DbSession
from app.errors import DB_UNAVAILABLE_MESSAGE, register_exception_handlers
from app.logging_config import setup_logging
from app.routers import auth, material_units, reports, storage_units, users
from app.routers.references import reference_routers

DESCRIPTION = """
Серверная часть информационной системы автоматизации складского учета материалов
(ТЗ-ИС-СКЛАД-01). 
"""

setup_logging(get_settings().log_level)

app = FastAPI(title="ИС «Склад»", version="1.0.0", description=DESCRIPTION)
register_exception_handlers(app)

app.include_router(auth.router)
app.include_router(users.router)
for reference_router in reference_routers:
    app.include_router(reference_router)
app.include_router(material_units.router)
app.include_router(storage_units.router)
app.include_router(reports.router)


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def index() -> str:
    return "<h1>ИС «Склад»</h1><p>Сервер запущен. Описание API: <a href='/docs'>/docs</a>.</p>"


@app.get("/health", tags=["Диагностика"], summary="Проверка приложения и БД")
def health(session: DbSession) -> dict[str, str]:
    try:
        session.execute(text("SELECT 1"))
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail=DB_UNAVAILABLE_MESSAGE) from None
    return {"status": "ok", "database": "ok"}
