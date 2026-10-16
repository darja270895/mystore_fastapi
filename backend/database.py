#Syncronious DB connections
# from sqlalchemy import create_engine
# from sqlalchemy.orm import declarative_base, sessionmaker
#
# SQLALCHEMY_DATABASE_URL = "sqlite:///./sql_app.db"
#
# engine = create_engine(
#     SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
# )
#
# SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
#
# Base = declarative_base()
#
# #get DB session for each request
# def get_db():
#     db = SessionLocal()
#     try:
#         yield db
#     finally:
#         db.close()

'''Async SQLAlchemy engine + per-request session factory.

Multi-worker notes (SQLite):
- Each uvicorn worker is a separate process sharing one .db file.
- Use NullPool (no cross-process connection sharing).
- Enable WAL + busy_timeout so writers wait instead of failing immediately.
'''

from collections.abc import AsyncGenerator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from backend.config import settings

engine = create_async_engine(
    settings.SQLALCHEMY_DATABASE_URL,
    echo=settings.SQL_ECHO,
    poolclass=NullPool,
    connect_args={"timeout": 30},
)


@event.listens_for(engine.sync_engine, "connect")
def _sqlite_on_connect(dbapi_connection, _connection_record) -> None:
    cursor = dbapi_connection.cursor()

    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=30000")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()


AsyncSessionLocal = async_sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    '''One AsyncSession per request never share across concurrent tasks'''
    async with AsyncSessionLocal() as session:
                yield session
