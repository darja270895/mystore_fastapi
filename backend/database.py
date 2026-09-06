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
from typing import AsyncGenerator

#Async SQLite connection
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase


# SQLALCHEMY_DATABASE_URL = "sqlite:///./sql_app.db"

#Async DB connection URL, + DB name specifying
SQLALCHEMY_DATABASE_URL = "sqlite+aiosqlite:///./sql_app.db" # aiosqlite - async interface for SQLite

# async движок
engine = create_async_engine(SQLALCHEMY_DATABASE_URL, echo=True) #echo=True вывод в консоль сгенерированные запросы
# engine = create_async_engine(SQLALCHEMY_DATABASE_URL) #echo=True вывод в консоль сгенерированные запросы

# fabric method to generate asyncSession instances
AsyncSessionLocal = async_sessionmaker(
    autocommit=False,
    autoflush=False, #flush - отправляет накопленные в памяти изменения но не делает commit.
    bind=engine,
    class_=AsyncSession,  # Explicitly tell it to generate async sessions
    expire_on_commit=False, #атрибуты не протухают после коммита, асинхронная сессия может брать значение из памяти а не из БД

)

# Base = declarative_base()

#формирует будущие сессии по запросу
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Create session for every query and closes this session after query executes
    :return:
    """
    async with AsyncSessionLocal() as session: #async context manager
        yield session