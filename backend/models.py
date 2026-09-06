from typing import Optional

from sqlalchemy import Column, Integer, String, BigInteger, ForeignKey, DateTime, Numeric
from datetime import datetime
from sqlalchemy.orm import relationship, DeclarativeBase, declared_attr, Mapped, mapped_column


class Base(DeclarativeBase):
    """
    SQLAlchemy 2.0 standart.
    Instrument for Alembic migrations.
    Passes Base.metadata for all Objects that are inherited from Base class and generate Alembic migrations.
    Turns Data classes into SQAlchemy ORMs.
    """
    @declared_attr.directive
    def __tablename__(cls) -> str:
        """
            set default tablename style for all inherited classes
        """
        return cls.__name__.lower()

    created_at: Mapped[Optional[datetime]] = mapped_column(default=datetime.utcnow)

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    email = Column(String, unique=True, index=True)

class Product(Base):
    __tablename__='items'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    stock = Column(Integer, nullable=False, default=0)
    price = Column(Numeric(10, 2), nullable=False, default=0)


class Purchase(Base):
    __tablename__='purchases'
    id = Column(BigInteger, primary_key=True)
    user_id=Column(BigInteger, nullable=False)
    product_id = Column(Integer, ForeignKey('items.id'), nullable=False)
    amount = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    product = (relationship(Product))

