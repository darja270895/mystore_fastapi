from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db

from .schemas import UserCreate, UserResponse
from .service import UserService

""" 
Отвечает за HTTP. 
Путь:
    HTTP Request -> Schema -> Service -> Response
"""

router = APIRouter(
    prefix="/users",
    tags=["Users"]
)


def get_user_service(
        db: AsyncSession = Depends(get_db)
) -> UserService:
    return UserService(db_session=db)


@router.post("/", response_model=UserResponse)
async def create_user(user_data: UserCreate, service: UserService = Depends(get_user_service)):
    return await service.create_user(user_data=user_data)

@router.get("/", response_model=list[UserResponse])
async def get_all_users(service: UserService = Depends(get_user_service)):
    return await service.get_all_users()

@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: int, service: UserService = Depends(get_user_service)):
    return await service.get_user(user_id)


