FROM python:3.12-slim

WORKDIR /app

# System deps for building some wheels if needed
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt

RUN pip install --no-cache-dir -r /app/requirements.txt

# Keep package import path: `backend.main:app`
COPY . /app/backend/
COPY entrypoint.sh /app/entrypoint.sh

RUN chmod +x /app/entrypoint.sh \
    && sed -i 's/\r$//' /app/entrypoint.sh \
    && mkdir -p /app/data

ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    UVICORN_WORKERS=4 \
    SQLALCHEMY_DATABASE_URL=sqlite+aiosqlite:////app/data/sql_app.db \
    REDIS_HOST=redis \
    REDIS_PORT=6379

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
