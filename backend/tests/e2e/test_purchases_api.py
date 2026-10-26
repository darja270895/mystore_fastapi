"""End-to-end tests for the purchase pipeline and its read models."""

import pytest


@pytest.fixture
async def user_and_product(api_client):
    user = await api_client.post("/users/", json={"name": "Ann", "email": "ann@example.com"})
    product = await api_client.post(
        "/products/", json={"name": "Keyboard", "stock": 5, "price": 25}
    )
    return user.json(), product.json()


async def test_purchase_updates_stock_and_read_models(
    api_client, fake_adapters, user_and_product
):
    user, product = user_and_product

    created = await api_client.post(
        "/purchases/",
        json={"user_id": user["id"], "product_id": product["id"], "amount": 2},
    )

    assert created.status_code == 201
    purchase = created.json()
    assert purchase["amount"] == 2

    assert (await api_client.get(f"/products/{product['id']}")).json()["stock"] == 3

    listed = await api_client.get("/purchases/")
    assert [row["id"] for row in listed.json()] == [purchase["id"]]

    movements = await api_client.get(
        "/purchases/stock-movements", params={"product_id": product["id"]}
    )
    assert [(row["delta"], row["reason"]) for row in movements.json()] == [(-2, "purchase")]

    recent = await api_client.get("/purchases/recent")
    assert recent.json()[0]["purchase_id"] == purchase["id"]
    assert recent.json()[0]["total_price"] == 50.0

    assert len(fake_adapters.purchase_events.dispatched) == 1


async def test_insufficient_stock_is_rejected(api_client, user_and_product):
    user, product = user_and_product

    response = await api_client.post(
        "/purchases/",
        json={"user_id": user["id"], "product_id": product["id"], "amount": 99},
    )

    assert response.status_code == 400
    assert "Insufficient stock" in response.json()["detail"]


async def test_rate_limit_returns_429(api_client, fake_adapters, user_and_product):
    user, product = user_and_product
    fake_adapters.purchase_coordinator.limit = 1
    payload = {"user_id": user["id"], "product_id": product["id"], "amount": 1}

    assert (await api_client.post("/purchases/", json=payload)).status_code == 201

    throttled = await api_client.post("/purchases/", json=payload)

    assert throttled.status_code == 429
    assert "Rate limit" in throttled.json()["detail"]


async def test_locked_stock_returns_409(api_client, fake_adapters, user_and_product):
    user, product = user_and_product
    await fake_adapters.purchase_coordinator.acquire_stock_lock(product["id"], "other")

    response = await api_client.post(
        "/purchases/",
        json={"user_id": user["id"], "product_id": product["id"], "amount": 1},
    )

    assert response.status_code == 409


async def test_unknown_user_or_product_returns_404(api_client, user_and_product):
    user, product = user_and_product

    missing_user = await api_client.post(
        "/purchases/", json={"user_id": 4242, "product_id": product["id"], "amount": 1}
    )
    missing_product = await api_client.post(
        "/purchases/", json={"user_id": user["id"], "product_id": 4242, "amount": 1}
    )

    assert missing_user.status_code == 404
    assert missing_product.status_code == 404


async def test_zero_amount_is_rejected_by_validation(api_client, user_and_product):
    user, product = user_and_product

    response = await api_client.post(
        "/purchases/",
        json={"user_id": user["id"], "product_id": product["id"], "amount": 0},
    )

    assert response.status_code == 422


async def test_recent_feed_is_empty_without_redis(api_client_without_redis):
    response = await api_client_without_redis.get("/purchases/recent")

    assert response.status_code == 200
    assert response.json() == []


async def test_purchase_works_without_redis(api_client_without_redis):
    user = await api_client_without_redis.post(
        "/users/", json={"name": "Ann", "email": "ann@example.com"}
    )
    product = await api_client_without_redis.post(
        "/products/", json={"name": "Keyboard", "stock": 5, "price": 25}
    )

    created = await api_client_without_redis.post(
        "/purchases/",
        json={
            "user_id": user.json()["id"],
            "product_id": product.json()["id"],
            "amount": 1,
        },
    )

    assert created.status_code == 201


async def test_notifications_endpoint_returns_consumer_output(
    api_client, session_factory, user_and_product
):
    from backend import models

    user, _ = user_and_product
    async with session_factory() as session:
        session.add(
            models.Notification(
                user_id=user["id"],
                kind="purchase_confirmed",
                payload='{"purchase_id": 1}',
                is_read=False,
            )
        )
        await session.commit()

    response = await api_client.get(f"/purchases/notifications/{user['id']}")

    assert response.status_code == 200
    assert response.json()[0]["kind"] == "purchase_confirmed"
    assert response.json()[0]["is_read"] is False


async def test_notifications_are_scoped_to_the_user(api_client, user_and_product):
    response = await api_client.get("/purchases/notifications/4242")

    assert response.status_code == 200
    assert response.json() == []
