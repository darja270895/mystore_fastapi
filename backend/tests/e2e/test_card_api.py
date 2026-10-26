"""End-to-end tests for /card, including checkout and the SSE stream."""

import json

import pytest

from backend.card.card_events import CardEvent
from backend.tests.fakes import CARD_CHANNEL


@pytest.fixture
async def user_and_products(api_client):
    user = await api_client.post("/users/", json={"name": "Ann", "email": "ann@example.com"})
    keyboard = await api_client.post(
        "/products/", json={"name": "Keyboard", "stock": 5, "price": 25}
    )
    mouse = await api_client.post("/products/", json={"name": "Mouse", "stock": 5, "price": 10})
    return user.json(), keyboard.json(), mouse.json()


async def test_add_remove_and_clear_card(api_client, user_and_products):
    user, keyboard, mouse = user_and_products

    added = await api_client.post(
        "/card/add",
        json={"user_id": user["id"], "product_id": keyboard["id"], "amount": 2},
    )

    assert added.status_code == 201
    body = added.json()
    assert body["status"] == "queued"
    assert body["channel"] == CARD_CHANNEL
    assert body["card"]["total_items"] == 2
    assert body["card"]["items"][0]["product_name"] == "Keyboard"

    await api_client.post(
        "/card/add", json={"user_id": user["id"], "product_id": mouse["id"], "amount": 1}
    )
    card = await api_client.get(f"/card/{user['id']}")
    assert card.json()["total_items"] == 3

    removed = await api_client.post(
        "/card/remove", json={"user_id": user["id"], "product_id": keyboard["id"]}
    )
    assert removed.status_code == 200
    assert removed.json()["card"]["total_items"] == 1

    cleared = await api_client.post(f"/card/clear/{user['id']}")
    assert cleared.status_code == 200
    assert cleared.json()["card"]["items"] == []


async def test_empty_card_is_returned_for_a_new_user(api_client):
    response = await api_client.get("/card/77")

    assert response.status_code == 200
    assert response.json() == {"user_id": 77, "items": [], "total_items": 0}


async def test_adding_an_unknown_product_returns_404(api_client, user_and_products):
    user, _, _ = user_and_products

    response = await api_client.post(
        "/card/add", json={"user_id": user["id"], "product_id": 4242, "amount": 1}
    )

    assert response.status_code == 404


async def test_card_endpoints_are_unavailable_without_redis(api_client_without_redis):
    assert (await api_client_without_redis.get("/card/1")).status_code == 503
    assert (
        await api_client_without_redis.post(
            "/card/add", json={"user_id": 1, "product_id": 1, "amount": 1}
        )
    ).status_code == 503
    assert (await api_client_without_redis.post("/card/clear/1")).status_code == 503
    assert (await api_client_without_redis.post("/card/checkout/1")).status_code == 503


async def test_checkout_buys_the_card_and_empties_it(api_client, user_and_products):
    user, keyboard, mouse = user_and_products
    await api_client.post(
        "/card/add", json={"user_id": user["id"], "product_id": keyboard["id"], "amount": 2}
    )
    await api_client.post(
        "/card/add", json={"user_id": user["id"], "product_id": mouse["id"], "amount": 1}
    )

    response = await api_client.post(f"/card/checkout/{user['id']}")

    assert response.status_code == 201
    purchases = response.json()
    assert sorted(purchase["amount"] for purchase in purchases) == [1, 2]

    assert (await api_client.get(f"/card/{user['id']}")).json()["total_items"] == 0
    assert (await api_client.get(f"/products/{keyboard['id']}")).json()["stock"] == 3
    assert (await api_client.get(f"/products/{mouse['id']}")).json()["stock"] == 4


async def test_checkout_of_an_empty_card_is_rejected(api_client, user_and_products):
    user, _, _ = user_and_products

    response = await api_client.post(f"/card/checkout/{user['id']}")

    assert response.status_code == 400


async def test_sse_stream_emits_ready_then_card_events(api_client, fake_adapters):
    event = CardEvent(action="add", user_id=1, product_id=2, amount=1, product_name="Book")
    fake_adapters.card_event_stream.messages_to_emit = [
        None,
        event.model_dump_json(),
    ]

    async with api_client.stream("GET", "/card/events/live") as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        body = "".join([chunk async for chunk in response.aiter_text()])

    events = parse_sse(body)
    assert events[0] == ("ready", {"stream": "card"})
    assert events[1] == ("ping", {"ok": True})
    assert events[2][0] == "card"
    assert events[2][1]["event_id"] == event.event_id


async def test_sse_stream_reports_an_error_without_redis(api_client_without_redis):
    async with api_client_without_redis.stream("GET", "/card/events/live") as response:
        body = "".join([chunk async for chunk in response.aiter_text()])

    assert parse_sse(body) == [("error", {"detail": "Redis unavailable"})]


def parse_sse(body: str) -> list[tuple[str, dict]]:
    events = []
    for block in body.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines())
        events.append((lines["event"], json.loads(lines["data"])))
    return events
