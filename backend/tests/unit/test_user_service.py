"""UserService unit tests."""

from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from backend import models
from backend.users.schemas import UserCreate
from backend.users.service import UserService


def make_user(user_id: int = 1, email: str = "buyer@example.com"):
    user = models.User(name="Buyer", email=email)
    user.id = user_id
    return user


@pytest.fixture
def service() -> UserService:
    service = UserService(db_session=AsyncMock())
    service.db_interface = AsyncMock()
    return service


async def test_create_user_rejects_duplicate_email(service):
    service.db_interface.get_by_email.return_value = make_user()

    with pytest.raises(HTTPException) as exc_info:
        await service.create_user(UserCreate(name="Buyer", email="buyer@example.com"))

    assert exc_info.value.status_code == 409
    service.db_interface.create_user.assert_not_awaited()


async def test_create_user_commits_new_row(service):
    service.db_interface.get_by_email.return_value = None
    service.db_interface.create_user.return_value = make_user(user_id=5)

    created = await service.create_user(UserCreate(name="Buyer", email="new@example.com"))

    assert created.id == 5
    service.db_session.commit.assert_awaited_once()
    service.db_session.refresh.assert_awaited_once()


async def test_get_user_returns_row_or_404(service):
    service.db_interface.get_by_id.return_value = make_user()
    assert (await service.get_user(1)).id == 1

    service.db_interface.get_by_id.return_value = None
    with pytest.raises(HTTPException) as exc_info:
        await service.get_user(404)
    assert exc_info.value.status_code == 404


async def test_get_all_users_delegates_to_repository(service):
    service.db_interface.get_all.return_value = [make_user(), make_user(user_id=2)]

    assert len(await service.get_all_users()) == 2
