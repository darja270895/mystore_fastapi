"""Repository layer for purchases, stock movements, and notifications."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import backend.models as models
from backend.purchases.purchase_schemas import PurchaseCreate


class PurchaseDbInterface:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_purchase(self, data: PurchaseCreate) -> models.Purchase:
        purchase = models.Purchase(
            user_id=data.user_id,
            product_id=data.product_id,
            amount=data.amount,
        )
        self.session.add(purchase)
        await self.session.flush()
        return purchase

    async def get_all(self) -> list[models.Purchase]:
        result = await self.session.execute(select(models.Purchase))
        return list(result.scalars().all())

    async def get_by_id(self, purchase_id: int) -> models.Purchase | None:
        result = await self.session.execute(
            select(models.Purchase).where(models.Purchase.id == purchase_id)
        )
        return result.scalar_one_or_none()

    async def get_user(self, user_id: int) -> models.User | None:
        result = await self.session.execute(
            select(models.User).where(models.User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_product(self, product_id: int) -> models.Product | None:
        result = await self.session.execute(
            select(models.Product).where(models.Product.id == product_id)
        )
        return result.scalar_one_or_none()

    async def decrement_stock(self, product: models.Product, amount: int) -> models.Product:
        product.stock -= amount
        await self.session.flush()
        return product

    async def create_stock_movement(
        self,
        *,
        product_id: int,
        delta: int,
        reason: str,
        purchase_id: int | None,
    ) -> models.StockMovement:
        movement = models.StockMovement(
            product_id=product_id,
            delta=delta,
            reason=reason,
            purchase_id=purchase_id,
        )
        self.session.add(movement)
        await self.session.flush()
        return movement

    async def list_stock_movements(self, product_id: int | None = None) -> list[models.StockMovement]:
        statement = select(models.StockMovement).order_by(models.StockMovement.id.desc())
        if product_id is not None:
            statement = statement.where(models.StockMovement.product_id == product_id)
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def list_notifications(self, user_id: int) -> list[models.Notification]:
        result = await self.session.execute(
            select(models.Notification)
            .where(models.Notification.user_id == user_id)
            .order_by(models.Notification.id.desc())
        )
        return list(result.scalars().all())
