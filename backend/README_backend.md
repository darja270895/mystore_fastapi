## Deployment (PRODUCTION BUILD)

From **repo root** (`mystore_fastapi/`):

```text
Deployment
    │
    ▼
Run Alembic migrations
    │
    ▼
Start Uvicorn (--workers 4)
    │
    ├── Worker 1  (may own Redis stream consumer)
    ├── Worker 2  (HTTP only)
    ├── Worker 3  (HTTP only)
    └── Worker 4  (HTTP only)
            │
            ▼
        SQLite DB (WAL mode)
```

### 1) Migrate once (before workers start)

*When Initial Migration

```bash
cd backend
..\backend\.venv\Scripts\activate   # or: backend\.venv\Scripts\activate from root
python -m alembic revision --autogenerate -m "initial" Начальная миграция
```

*Else

```bash
cd backend
..\backend\.venv\Scripts\activate   # or: backend\.venv\Scripts\activate from root
python -m alembic upgrade head
```

From repo root with uv:

```bash
uv run --directory backend alembic upgrade head
```

## Prefer Docker for multi-worker (works on Windows host)

Native Windows `uvicorn --workers 4` is broken (`WinError 10022`).
Use Docker (Linux containers) instead:

Пересборка и запуск нового контейнера

```bash
cd backend

docker compose --profile tools up -d
time docker compose up -d
```

Запуск контейнера

```bash
cd backend
docker compose up --build
```

Then open:

- http://127.0.0.1:8000/
- http://127.0.0.1:8000/docs

Check 4 workers:

```bash
docker compose logs api | findstr /I worker
# or Git Bash:
docker compose logs api | grep -i "Started server process"
```

Stop:

```bash
docker compose down
```

Change worker count in `docker-compose.yaml` (`UVICORN_WORKERS`) or:

```bash
UVICORN_WORKERS=2 docker compose up --build
```

Flow inside the container:

```text
entrypoint.sh
    │
    ▼
alembic upgrade head
    │
    ▼
uvicorn backend.main:app --workers N
    │
    ├── Worker 1 (+ optional Redis stream consumer leader)
    ├── Worker 2
    ├── …
    └── Redis service (same compose network)
            │
            ▼
    SQLite at /app/data/sql_app.db (named volume)
```

### Native Windows (single worker only)

```bash
# from repo root
docker compose -f backend/docker-compose.yaml up -d redis
uv run --env-file backend/.env uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers 1 --loop asyncio
```

### Rules that avoid conflicts


| Conflict                                        | Fix in this project                                   |
| ----------------------------------------------- | ----------------------------------------------------- |
| `create_all` vs Alembic racing across 4 workers | Removed from lifespan — migrate before start         |
| 4 stream consumers → duplicate notifications   | Redis leader lock — only one worker runs consumer    |
| SQLite write locks with many processes          | `NullPool` + `PRAGMA journal_mode=WAL` + busy_timeout |
| `--reload` + `--workers`                        | Mutually exclusive; reload forces 1 worker            |
| `uvicorn main:app` from `backend/`              | Wrong — use`backend.main:app` from repo root         |

### Dev (single process, hot reload)

```bash
# from repo root
set UVICORN_RELOAD=true
python -m backend.main
# or:
fastapi dev backend/main.py
fastapi dev #?????
```

## Migrations (new revision)

```bash
cd backend
python -m alembic revision --autogenerate -m "describe your change"
python -m alembic upgrade head
```

## Packages

```bash
uv pip install --python .venv <package>
uv pip list --python .venv 

pip freeze > requirements.txt
```

**Redis + AsyncIO study guide:** see `REDIS_ASYNCIO_LEARNING.md`
