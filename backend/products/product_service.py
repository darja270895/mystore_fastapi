from sqlalchemy.ext.asyncio import AsyncSession

from backend.products.product_db_interface import ProductDbInterface
from backend.products.product_schemas import ProductCreate, ProductResponse
from fastapi import HTTPException, Depends

from backend.redis_app.redis_service import RedisService

""" Основная Бизнес-логика. Объединяет Интерфейс взаимодействия с БД и Бизнес-логику"""

class ProductService:

    def __init__(self, db_session: AsyncSession, redis:RedisService):
        self.db_session =  db_session
        self._cache = redis
        self.db_interface = ProductDbInterface(db_session)

    async def create_product(self, product_data: ProductCreate):
        existing_product = await self.db_interface.get_by_name(product_name=product_data.name)
        if existing_product:
            raise HTTPException(status_code=409,  detail = "Product with this name already exists")
        product_obj = await self.db_interface.create_product(product_data)

        await self.db_session.commit()
        await self.db_session.refresh(product_obj)

        product_response = ProductResponse.model_validate(product_obj)
        serialized_product_obj = product_response.model_dump()
        if self._cache:
            await self._cache.set_value(key=f"product_{product_obj.id}", value=serialized_product_obj, ex=3600)

        return product_obj

    async def get_by_name(self, product_name: str):

        product_obj = await self.db_interface.get_by_name(product_name=product_name)
        #переписать по паттерну Стратегия
        if product_obj:
            return product_obj
        else:
            raise HTTPException(status_code=404, detail="Product not found")

    async def get_by_id(self, product_id: int):

        #search in Redis firstly
        if self._cache:
            cached_obj = await self._cache.get_value(key=f"product_{product_id}")
            if cached_obj is not None:
                return cached_obj

        # select from DB
        product_obj = await self.db_interface.get_by_id(product_id=product_id)
        if product_obj is None:
            raise HTTPException (
                status_code=404,
                detail="Product not found"
            )

        product_response  = ProductResponse.model_validate(product_obj)
        if self._cache:
            await self._cache.set_value(key=f"product_{product_id}", value=product_response.model_dump(), ex=3600)

        return product_obj

    async def get_all_products(self):
        return await self.db_interface.get_all()

    async def delete_product(self):
        ...