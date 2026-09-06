""" Работа с БД """
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import backend.models as models
from backend.users.schemas import UserCreate


class UserDBInterface:

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_user(self, userdata: UserCreate) -> models.User:
        new_user = models.User(name=userdata.name, email=userdata.email)
        self.session.add(new_user)
        await self.session.flush() #добавляем User в текущую транзакцию
        return new_user

    async def get_all(self):
        statement = select(models.User)
        all_users = await self.session.execute(statement)

        return all_users.scalars().all() #returns clean objects list without tuple unpacking

    async def get_by_id(self, user_id: int) -> Optional[models.User]:
        """ Get user by passed id. Async function."""
        statement = select(models.User).where(models.User.id == user_id)
        res = await self.session.execute(statement)

        return res.scalar_one_or_none() #returns clean object without tuple unpacking

    async def get_by_email(self, email: str) -> Optional[models.User]:
        """ Get user by passed email. Async function."""
        statement = select(models.User).where(models.User.email == email)
        res = await self.session.execute(statement)

        return res.scalar_one_or_none() #returns clean object without tuple unpacking
