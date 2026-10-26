"""Shared fixtures for unit, integration and end-to-end tests.

Databases: every test gets a throwaway SQLite file, and the application session
factory is redirected to it (including the module-level factories used by the
purchase pipeline and the stream consumer).

Redis: integration tests use a real server on a dedicated database index
(``TEST_REDIS_DB``, default 15) and skip when no server is reachable.
"""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator

import pytest
import redis.asyncio as asyncredis
from httpx import ASGITransport, AsyncClient
from redis.exceptions import RedisError
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

import backend.database as database_module
import backend.redis_app.stream_consumer as stream_consumer_module
from backend import models
from backend.config import settings
from backend.purchases import purchase_service as purchase_service_module
from backend.redis_app.adapters import build_redis_adapters
from backend.tests.fakes import FakeAdapters

TEST_REDIS_DB = int(os.getenv("TEST_REDIS_DB", "15"))


# --------------------------------------------------------------------------- #
# Database
# --------------------------------------------------------------------------- #
@pytest.fixture
async def db_engine(tmp_path):
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path / 'test.db'}",
        poolclass=NullPool,
        connect_args={"timeout": 30},
    )

    @event.listens_for(engine.sync_engine, "connect")
    def _sqlite_pragmas(dbapi_connection, _record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.close()

    async with engine.begin() as connection:
        await connection.run_sync(models.Base.metadata.create_all)

    yield engine

    await engine.dispose()


@pytest.fixture
async def session_factory(db_engine, monkeypatch):
    """Point every application session factory at the throwaway database."""
    factory = async_sessionmaker(
        bind=db_engine,
        class_=AsyncSession,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
    )
    monkeypatch.setattr(database_module, "AsyncSessionLocal", factory)
    monkeypatch.setattr(purchase_service_module, "AsyncSessionLocal", factory)
    monkeypatch.setattr(stream_consumer_module, "AsyncSessionLocal", factory)
    return factory


@pytest.fixture
async def db_session(session_factory) -> AsyncGenerator[AsyncSession, None]:
    async with session_factory() as session:
        yield session


@pytest.fixture
async def seed(session_factory):
    """Insert a committed user and product, as the purchase pipeline expects."""

    async def _seed(
        *,
        user_email: str = "buyer@example.com",
        product_name: str = "Keyboard",
        stock: int = 10,
        price: float = 25.0,
    ) -> tuple[models.User, models.Product]:
        async with session_factory() as session:
            user = models.User(name="Buyer", email=user_email)
            product = models.Product(name=product_name, stock=stock, price=price)
            session.add_all([user, product])
            await session.commit()
            await session.refresh(user)
            await session.refresh(product)
            return user, product

    return _seed


# --------------------------------------------------------------------------- #
# Ports (in-memory)
# --------------------------------------------------------------------------- #
@pytest.fixture
def fake_adapters() -> FakeAdapters:
    return FakeAdapters()


# --------------------------------------------------------------------------- #
# Redis (real server)
# --------------------------------------------------------------------------- #
@pytest.fixture
async def redis_client() -> AsyncGenerator[asyncredis.Redis, None]:
    client = asyncredis.Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        db=TEST_REDIS_DB,
        decode_responses=True,
        socket_timeout=settings.REDIS_SOCKET_TIMEOUT,
        socket_connect_timeout=1.0,
    )
    try:
        await client.ping()
    except (RedisError, OSError):
        await client.aclose()
        pytest.skip(f"Redis is unavailable on {settings.REDIS_HOST}:{settings.REDIS_PORT}")

    await client.flushdb()
    try:
        yield client
    finally:
        await client.flushdb()
        await client.aclose()


@pytest.fixture
async def redis_adapters(redis_client):
    return build_redis_adapters(redis_client)


# --------------------------------------------------------------------------- #
# End-to-end HTTP client
# --------------------------------------------------------------------------- #
@pytest.fixture
async def api_client(session_factory, fake_adapters, monkeypatch):
    """ASGI client running the real app, lifespan included, with fake ports."""
    monkeypatch.setattr(settings, "USE_REDIS", False)

    from backend.dependencies import get_redis_adapters
    from backend.main import app

    app.dependency_overrides[get_redis_adapters] = lambda: fake_adapters
    try:
        async with app.router.lifespan_context(app):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                yield client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
async def api_client_without_redis(session_factory, monkeypatch):
    """Same app, but every Redis-backed port is unavailable."""
    monkeypatch.setattr(settings, "USE_REDIS", False)

    from backend.dependencies import get_redis_adapters
    from backend.main import app

    app.dependency_overrides[get_redis_adapters] = lambda: None
    try:
        async with app.router.lifespan_context(app):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                yield client
    finally:
        app.dependency_overrides.clear()
