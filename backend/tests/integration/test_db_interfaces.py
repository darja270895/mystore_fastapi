"""Repository integration tests against a real (throwaway) SQLite database."""

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from backend import models
from backend.products.product_db_interface import ProductDbInterface
from backend.products.product_schemas import ProductCreate
from backend.purchases.purchase_db_interface import PurchaseDbInterface
from backend.purchases.purchase_schemas import PurchaseCreate
from backend.users.db_interface import UserDBInterface
from backend.users.schemas import UserCreate


class TestUserRepository:
    async def test_create_and_read_back(self, db_session):
        repository = UserDBInterface(db_session)

        created = await repository.create_user(UserCreate(name="Ann", email="ann@example.com"))
        await db_session.commit()

        assert created.id is not None
        assert created.created_at is not None
        assert (await repository.get_by_id(created.id)).email == "ann@example.com"
        assert (await repository.get_by_email("ann@example.com")).id == created.id
        assert len(await repository.get_all()) == 1

    async def test_missing_rows_return_none(self, db_session):
        repository = UserDBInterface(db_session)

        assert await repository.get_by_id(999) is None
        assert await repository.get_by_email("nobody@example.com") is None

    async def test_unique_email_is_enforced_by_the_schema(self, db_session):
        repository = UserDBInterface(db_session)
        await repository.create_user(UserCreate(name="Ann", email="ann@example.com"))
        await db_session.commit()

        with pytest.raises(IntegrityError):
            await repository.create_user(UserCreate(name="Other", email="ann@example.com"))


class TestProductRepository:
    async def test_create_read_and_delete(self, db_session):
        repository = ProductDbInterface(db_session)

        product = await repository.create_product(
            ProductCreate(name="Desk", stock=4, price=99)
        )
        await db_session.commit()

        assert (await repository.get_by_id(product.id)).name == "Desk"
        assert (await repository.get_by_name("Desk")).id == product.id
        assert len(await repository.get_all()) == 1

        await repository.delete(product)
        await db_session.commit()

        assert await repository.get_by_id(product.id) is None

    async def test_duplicate_names_are_a_service_rule_not_a_schema_rule(self, db_session):
        """`items.name` has no unique index — ProductService guards it instead."""
        repository = ProductDbInterface(db_session)
        await repository.create_product(ProductCreate(name="Desk", stock=1, price=1))
        await repository.create_product(ProductCreate(name="Desk", stock=2, price=2))
        await db_session.commit()

        assert len(await repository.get_all()) == 2


class TestPurchaseRepository:
    async def test_purchase_stock_movement_and_notification_round_trip(
        self, db_session, seed
    ):
        user, product = await seed(stock=10)
        repository = PurchaseDbInterface(db_session)

        purchase = await repository.create_purchase(
            PurchaseCreate(user_id=user.id, product_id=product.id, amount=3)
        )
        stored_product = await repository.get_product(product.id)
        await repository.decrement_stock(stored_product, 3)
        movement = await repository.create_stock_movement(
            product_id=product.id, delta=-3, reason="purchase", purchase_id=purchase.id
        )
        db_session.add(
            models.Notification(
                user_id=user.id, kind="purchase_confirmed", payload="{}", is_read=False
            )
        )
        await db_session.commit()

        assert purchase.id is not None
        assert (await repository.get_by_id(purchase.id)).amount == 3
        assert (await repository.get_product(product.id)).stock == 7
        assert (await repository.get_user(user.id)).id == user.id
        assert len(await repository.get_all()) == 1
        assert [row.id for row in await repository.list_stock_movements()] == [movement.id]
        assert len(await repository.list_notifications(user.id)) == 1

    async def test_stock_movements_can_be_filtered_by_product(self, db_session, seed):
        _, first = await seed(product_name="First")
        _, second = await seed(user_email="other@example.com", product_name="Second")
        repository = PurchaseDbInterface(db_session)

        await repository.create_stock_movement(
            product_id=first.id, delta=-1, reason="purchase", purchase_id=None
        )
        await repository.create_stock_movement(
            product_id=second.id, delta=-2, reason="purchase", purchase_id=None
        )
        await db_session.commit()

        filtered = await repository.list_stock_movements(product_id=second.id)

        assert [row.product_id for row in filtered] == [second.id]
        assert len(await repository.list_stock_movements()) == 2

    async def test_notifications_are_scoped_per_user_newest_first(self, db_session, seed):
        user, _ = await seed()
        db_session.add_all(
            [
                models.Notification(user_id=user.id, kind="a", payload="{}", is_read=False),
                models.Notification(user_id=user.id, kind="b", payload="{}", is_read=False),
            ]
        )
        await db_session.commit()
        repository = PurchaseDbInterface(db_session)

        rows = await repository.list_notifications(user.id)

        assert [row.kind for row in rows] == ["b", "a"]
        assert await repository.list_notifications(user.id + 999) == []

    async def test_purchase_requires_an_existing_product(self, db_session, seed):
        user, _ = await seed()
        repository = PurchaseDbInterface(db_session)

        with pytest.raises(IntegrityError):
            await repository.create_purchase(
                PurchaseCreate(user_id=user.id, product_id=4242, amount=1)
            )

    async def test_deleting_a_product_cascades_to_its_purchases(self, db_session, seed):
        user, product = await seed()
        repository = PurchaseDbInterface(db_session)
        await repository.create_purchase(
            PurchaseCreate(user_id=user.id, product_id=product.id, amount=1)
        )
        await db_session.commit()

        await ProductDbInterface(db_session).delete(await repository.get_product(product.id))
        await db_session.commit()

        remaining = await db_session.execute(select(models.Purchase))
        assert remaining.scalars().all() == []
