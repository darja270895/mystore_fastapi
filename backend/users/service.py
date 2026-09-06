""" Бизнес-логика """

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from .db_interface import UserDBInterface
from .schemas import UserCreate

class UserService:
    def __init__(self, db_session: AsyncSession):
        self.db_interface = UserDBInterface(db_session) #переделать на Depends
        self.db_session = db_session

    async def create_user(self, user_data: UserCreate):

        existing_user = await self.db_interface.get_by_email(user_data.email)

        if existing_user:
            raise HTTPException(status_code=409, detail="User already exist")

        user_obj = await self.db_interface.create_user(user_data)

        await self.db_session.commit()
        await self.db_session.refresh(user_obj)

        return user_obj

    async def get_user(self, user_id: int):
        user_obj = await self.db_interface.get_by_id(user_id=user_id)
        #переписать по паттерну Стратегия
        if user_obj:
            return user_obj
        else:
            raise HTTPException(status_code=404, detail="User not found")

    async def get_all_users(self):
        return await self.db_interface.get_all()

