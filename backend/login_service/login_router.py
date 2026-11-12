"""
Отвечает за HTTP.
Путь:
    HTTP Request -> Schema -> Service -> Response

Two routers:
  /auth/*    public API (register, login) + endpoints other services call (verify, me)
  /health/*  Kubernetes probes
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.login_service.login_config import login_settings
from backend.login_service.login_dependencies import get_login_service
from backend.login_service.login_schemas import (
    AccountCreate,
    AccountResponse,
    HealthResponse,
    LoginRequest,
    TokenResponse,
    VerifyRequest,
    VerifyResponse,
)
from backend.login_service.login_service import LoginService

router = APIRouter(prefix="/auth", tags=["Auth"])
health_router = APIRouter(prefix="/health", tags=["Health"])

# auto_error=False: a missing header must be a 401 (not FastAPI's default 403).
bearer_scheme = HTTPBearer(auto_error=False)


def get_bearer_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> str:
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.credentials


@router.post("/register", response_model=AccountResponse, status_code=status.HTTP_201_CREATED)
async def register(data: AccountCreate, service: LoginService = Depends(get_login_service)):
    return await service.register(data)


@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest, service: LoginService = Depends(get_login_service)):
    return await service.login(data)


@router.post("/verify", response_model=VerifyResponse)
async def verify_token(data: VerifyRequest, service: LoginService = Depends(get_login_service)):
    """Token introspection for other services. Always 200; check `valid`."""
    return await service.verify(data.token)


@router.get("/me", response_model=AccountResponse)
async def get_me(
    token: str = Depends(get_bearer_token),
    service: LoginService = Depends(get_login_service),
):
    return await service.get_me(token)


@health_router.get("/livez", response_model=HealthResponse)
async def liveness_probe() -> HealthResponse:
    """livenessProbe: the process answers HTTP. Deliberately does not touch the database."""
    return HealthResponse(status="alive", pod=login_settings.POD_NAME)


@health_router.get("/startupz", response_model=HealthResponse)
async def startup_probe(request: Request, response: Response) -> HealthResponse:
    """startupProbe: 200 once lifespan startup (table creation) has finished."""
    started = bool(getattr(request.app.state, "login_started", False))
    if not started:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return HealthResponse(status="started" if started else "starting", pod=login_settings.POD_NAME)


@health_router.get("/readyz", response_model=HealthResponse)
async def readiness_probe(
    response: Response,
    service: LoginService = Depends(get_login_service),
) -> HealthResponse:
    """readinessProbe: can this pod reach its database? 503 takes it out of the Service."""
    try:
        await service.check_database()
    except Exception as exc:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return HealthResponse(status="not-ready", pod=login_settings.POD_NAME, detail=str(exc))
    return HealthResponse(status="ready", pod=login_settings.POD_NAME)
