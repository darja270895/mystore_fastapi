"""End-to-end tests for /users."""


async def test_create_read_and_list_users(api_client):
    created = await api_client.post(
        "/users/", json={"name": "Ann", "email": "ann@example.com"}
    )

    assert created.status_code == 200
    body = created.json()
    assert body["email"] == "ann@example.com"
    assert body["id"] > 0

    fetched = await api_client.get(f"/users/{body['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["name"] == "Ann"

    listed = await api_client.get("/users/")
    assert [user["id"] for user in listed.json()] == [body["id"]]


async def test_duplicate_email_is_rejected(api_client):
    payload = {"name": "Ann", "email": "ann@example.com"}
    await api_client.post("/users/", json=payload)

    conflict = await api_client.post("/users/", json=payload)

    assert conflict.status_code == 409
    assert "already" in conflict.json()["detail"].lower()


async def test_unknown_user_returns_404(api_client):
    response = await api_client.get("/users/4242")

    assert response.status_code == 404


async def test_invalid_payload_is_rejected_by_validation(api_client):
    response = await api_client.post("/users/", json={"name": "Ann"})

    assert response.status_code == 422
