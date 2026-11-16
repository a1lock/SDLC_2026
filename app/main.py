import os

import psycopg
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

app = FastAPI(title="ИС Склад", version="0.1.0")


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return "<h1>ИС «Склад»</h1><p>Прототип лабораторной работы № 2 запущен.</p>"


@app.get("/health")
def health() -> dict[str, str]:
    try:
        with psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=3) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
    except (KeyError, psycopg.Error):
        raise HTTPException(status_code=503, detail="База данных недоступна") from None
    return {"status": "ok", "database": "ok"}
