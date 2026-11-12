""" Работа с БД. Адаптер порта AccountRepository (SQLAlchemy). """

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.login_service.login_models import LoginAccount
from backend.login_service.login_ports import DuplicateAccountError
from backend.login_service.login_schemas import AccountRecord


class LoginDbInterface:

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_email(self, email: str) -> AccountRecord | None:
        statement = select(LoginAccount).where(LoginAccount.email == email)
        result = await self.session.execute(statement)
        account = result.scalar_one_or_none()
        return AccountRecord.model_validate(account) if account else None

    async def get_by_id(self, account_id: int) -> AccountRecord | None:
        statement = select(LoginAccount).where(LoginAccount.id == account_id)
        result = await self.session.execute(statement)
        account = result.scalar_one_or_none()
        return AccountRecord.model_validate(account) if account else None

    async def add(self, email: str, name: str, password_hash: str) -> AccountRecord:
        account = LoginAccount(email=email, name=name, password_hash=password_hash)
        self.session.add(account)
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise DuplicateAccountError(email) from exc
        return AccountRecord.model_validate(account)

    async def ping(self) -> None:
        await self.session.execute(text("SELECT 1"))
