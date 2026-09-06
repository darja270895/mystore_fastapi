""" Взаимодействие с БД"""
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import backend.models as models
from backend.products.product_schemas import ProductCreate, ProductResponse

class ProductDbInterface:

    def __init__(self, session: AsyncSession):
        self.session = session #пробрасываем сессию

    async def create_product(self, product_data: ProductCreate) -> models.Product:
        new_product = models.Product(name = product_data.name, stock = product_data.stock, price = product_data.price)
        self.session.add(new_product)
        await self.session.flush() #добавляем Product в текущую транзакцию

        return new_product

    async def get_all(self):
        statement = select(models.Product)
        all_products = await self.session.execute(statement)

        return all_products.scalars().all()

    async def get_by_id(self, product_id: int) -> Optional[ProductResponse]:
        statement = select(models.Product).where(models.Product.id == product_id)
        result = await self.session.execute(statement)

        return result.scalar_one_or_none() #returns clean object without tuple unpacking

    async def get_by_name(self, product_name: str) -> Optional[ProductResponse]:
        statement = select(models.Product).where(models.Product.name == product_name)
        result = await self.session.execute(statement)

        return result.scalar_one_or_none() #returns clean object without tuple unpacking