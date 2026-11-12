""" Формат входных и выходных данных login-сервиса (DTO). """

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class AccountCreate(BaseModel):
    """ POST /auth/register body """
    email: EmailStr
    name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    """ POST /auth/login body """
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class VerifyRequest(BaseModel):
    """ POST /auth/verify body — used by other services (see backend/auth_client.py) """
    token: str = Field(min_length=1)


class VerifyResponse(BaseModel):
    """ Token introspection result. An invalid token is a normal answer (HTTP 200, valid=false). """
    valid: bool
    user_id: int | None = None
    email: str | None = None
    expires_at: datetime | None = None


class AccountResponse(BaseModel):
    id: int
    email: str
    name: str

    model_config = {
        "from_attributes": True
    }


class AccountRecord(AccountResponse):
    """
    What the repository port hands to the core. Carries the password hash,
    so it is never returned over HTTP (the router always answers with AccountResponse).
    """
    password_hash: str
    is_active: bool = True


class IssuedToken(BaseModel):
    """ Result of the TokenIssuer port. """
    access_token: str
    expires_in: int


class TokenClaims(BaseModel):
    """ Verified contents of an access token. """
    account_id: int
    email: str
    expires_at: datetime


class HealthResponse(BaseModel):
    status: str
    service: str = "login"
    pod: str
    detail: str | None = None
