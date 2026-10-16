"""
ASGI application entrypoint.

Production-like flow (run from repo root):
  1) alembic upgrade head
  2) uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers 4

"""

from contextlib import AsyncExitStack, asynccontextmanager
import logging
from pathlib import Path
import sys
import uvicorn

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.card.card_router import router as card_router
from backend.config import settings
from backend.products.products_router import router as product_router
from backend.purchases.purchases_router import router as purchase_router
from backend.redis_app.redis_lifespan import redis_lifespan
from backend.users.user_router import router as user_router

logger = logging.getLogger(__name__)

@asynccontextmanager
async def main_lifespan(app: FastAPI):
    async with AsyncExitStack() as stack:
        if settings.USE_REDIS:
            await stack.enter_async_context(redis_lifespan(app))
            logger.info('Redis connection enabled ... ')
            
        yield
        logger.info('Exiting ... ')

app = FastAPI(
    title="MyStore FastAPI",
    description="Learning lab for Redis + AsyncIO on Python 3.13",
    lifespan = main_lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
INDEX_FILE = STATIC_DIR / "index.html"

app.mount("/frontend", StaticFiles(directory=STATIC_DIR), name="static")
app.include_router(user_router)
app.include_router(product_router)
app.include_router(card_router)
app.include_router(purchase_router)



@app.get("/")
async def read_root():
    if INDEX_FILE.exists():
        return FileResponse(
            INDEX_FILE,
            media_type="text/html",
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
        )
    return {"message": "Index file not found"}


if __name__ == "__main__":

    workers = 1 if settings.UVICORN_RELOAD else settings.UVICORN_WORKERS
    # uvicorn --workers uses shared sockets; that path is unreliable on native Windows
    # (WinError 10022). Use 1 worker locally, or run multi-worker in Docker/WSL.
    if sys.platform == "win32" and workers > 1:
        print(
            "WARNING: uvicorn --workers > 1 is unstable on native Windows "
            f"(requested {workers}). Falling back to 1 worker. "
            "For real multi-process: Docker or WSL2."
        )
        workers = 1

    uvicorn.run(
        "backend.main:app",
        host=settings.UVICORN_HOST,
        port=settings.UVICORN_PORT,
        workers=workers,
        reload=settings.UVICORN_RELOAD,
        loop="asyncio",
    )