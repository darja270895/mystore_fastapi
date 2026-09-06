Alembic migrations

python -m alembic revision --autogenerate -m "initial" Начальная миграция
python -m alembic upgrade head

Обновление requirements.txt

! Каждый раз при установке новых пакетов

pip freeze > requirements.txt

*Структура приложения (гексагональная архитектура)

**Запуск серверной части через uvmanager:

uv run fastapi dev main.py

PROD - not working for now

uv run fastapi run main,py --for Production build

or

uv run --env-file backend\.env uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers 4

or

uv run granian --interface asgi --workers 4 --bind 0.0.0.0:8000 main:app
