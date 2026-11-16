FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

RUN useradd --create-home --uid 1000 appuser
COPY alembic.ini ./
COPY migrations ./migrations
COPY app ./app
COPY scripts ./scripts
USER appuser

EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && python -m scripts.create_admin && exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]
