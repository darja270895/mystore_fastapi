"""
ASGI entrypoint of the login microservice. Runs as its own process / container / pod,
independently of backend.main.

Local run (from repo root):
  python -m backend.login_service.login_main
  uvicorn backend.login_service.login_main:app --port 8001

The main application talks to this service over HTTP (see backend/auth_client.py).
"""

from contextlib import asynccontextmanager
import logging
import sys

import uvicorn
from fastapi import FastAPI

from backend.login_service.login_config import INSECURE_DEV_JWT_SECRET, login_settings
from backend.login_service.login_database import login_engine
from backend.login_service.login_models import LoginBase
from backend.login_service.login_router import health_router, router as auth_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def login_lifespan(app: FastAPI):
    app.state.login_started = False

    if login_settings.LOGIN_JWT_SECRET == INSECURE_DEV_JWT_SECRET:
        logger.warning("LOGIN_JWT_SECRET is the built-in dev value — set a real secret before deploying")

    if login_settings.LOGIN_AUTO_CREATE_TABLES:
        async with login_engine.begin() as connection:
            await connection.run_sync(LoginBase.metadata.create_all)

    app.state.login_started = True
    yield
    app.state.login_started = False
    await login_engine.dispose()
    logger.info("Login service stopped")


app = FastAPI(
    title="MyStore Login Service",
    description="Authentication microservice: registration, login, token verification.",
    lifespan=login_lifespan,
)

app.include_router(auth_router)
app.include_router(health_router)


if __name__ == "__main__":
    workers = 1 if login_settings.LOGIN_RELOAD else login_settings.LOGIN_WORKERS
    # uvicorn --workers is unreliable on native Windows (WinError 10022); see backend/main.py.
    if sys.platform == "win32" and workers > 1:
        print(f"WARNING: uvicorn --workers > 1 is unstable on native Windows (requested {workers}). Using 1.")
        workers = 1

    uvicorn.run(
        "backend.login_service.login_main:app",
        host=login_settings.LOGIN_HOST,
        port=login_settings.LOGIN_PORT,
        workers=workers,
        reload=login_settings.LOGIN_RELOAD,
        loop="asyncio",
    )
