""" Бизнес-логика login-сервиса. Знает только про порты (login_ports), не про SQLAlchemy/JWT. """

from __future__ import annotations

import asyncio
import logging

from fastapi import HTTPException

from backend.login_service.login_ports import (
    AccountRepository,
    DuplicateAccountError,
    InvalidTokenError,
    PasswordHasher,
    TokenIssuer,
)
from backend.login_service.login_schemas import (
    AccountCreate,
    AccountRecord,
    LoginRequest,
    TokenResponse,
    VerifyResponse,
)

logger = logging.getLogger(__name__)


def _normalize_email(email: str) -> str:
    return email.strip().lower()


class LoginService:
    def __init__(
        self,
        accounts: AccountRepository,
        hasher: PasswordHasher,
        tokens: TokenIssuer,
    ):
        self.accounts = accounts
        self.hasher = hasher
        self.tokens = tokens

    async def register(self, data: AccountCreate) -> AccountRecord:
        email = _normalize_email(data.email)

        if await self.accounts.get_by_email(email):
            raise HTTPException(status_code=409, detail="Account already exists")

        # scrypt is CPU-bound: keep it off the event loop so other requests keep flowing.
        password_hash = await asyncio.to_thread(self.hasher.hash, data.password)

        try:
            return await self.accounts.add(email=email, name=data.name, password_hash=password_hash)
        except DuplicateAccountError:
            # Lost a race with a concurrent registration of the same e-mail.
            raise HTTPException(status_code=409, detail="Account already exists")

    async def login(self, data: LoginRequest) -> TokenResponse:
        account = await self.accounts.get_by_email(_normalize_email(data.email))

        # Always run a hash check (even for unknown e-mails) and give one generic error,
        # so neither timing nor the message reveals whether the e-mail is registered.
        password_ok = await asyncio.to_thread(
            self.hasher.verify,
            data.password,
            account.password_hash if account else None,
        )
        if account is None or not password_ok or not account.is_active:
            raise HTTPException(
                status_code=401,
                detail="Invalid email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        issued = self.tokens.issue(account)
        logger.info("Account %s logged in", account.id)
        return TokenResponse(access_token=issued.access_token, expires_in=issued.expires_in)

    async def verify(self, token: str) -> VerifyResponse:
        """Token introspection for other services. Never raises for a bad token."""
        try:
            claims = self.tokens.decode(token)
        except InvalidTokenError:
            return VerifyResponse(valid=False)

        # A valid signature is not enough: the account may have been deactivated since.
        account = await self.accounts.get_by_id(claims.account_id)
        if account is None or not account.is_active:
            return VerifyResponse(valid=False)

        return VerifyResponse(
            valid=True,
            user_id=account.id,
            email=account.email,
            expires_at=claims.expires_at,
        )

    async def get_me(self, token: str) -> AccountRecord:
        try:
            claims = self.tokens.decode(token)
        except InvalidTokenError:
            raise HTTPException(
                status_code=401,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        account = await self.accounts.get_by_id(claims.account_id)
        if account is None or not account.is_active:
            raise HTTPException(
                status_code=401,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return account

    async def check_database(self) -> None:
        """Readiness: raises if the database cannot be reached."""
        await self.accounts.ping()
