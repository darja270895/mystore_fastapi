from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column, relationship


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """
    SQLAlchemy 2.0 DeclarativeBase.
    All ORM models inherit this — Alembic reads Base.metadata.
    """

    @declared_attr.directive
    def __tablename__(cls) -> str:
        return cls.__name__.lower()

    created_at: Mapped[Optional[datetime]] = mapped_column(default=_utc_now)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, index=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)


class Product(Base):
    __tablename__ = "items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    stock: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)


class Purchase(Base):
    __tablename__ = "purchases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("items.id", ondelete="CASCADE"), nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)
    product: Mapped["Product"] = relationship("Product")


class StockMovement(Base):
    """
    Append-only inventory ledger.
    Every stock change (purchase, restock) leaves an auditable row.
    """

    __tablename__ = "stock_movements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("items.id", ondelete="CASCADE"), nullable=False, index=True)
    delta: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(64), nullable=False)
    purchase_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)


class Notification(Base):
    """
    User-facing notification created asynchronously by the Redis Stream consumer.
    Demonstrates the "event → background worker → DB write" pattern.
    """

    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[str] = mapped_column(Text, nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)
