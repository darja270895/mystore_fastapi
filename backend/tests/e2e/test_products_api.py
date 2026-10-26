"""End-to-end tests for /products, including the cache-TTL endpoint."""


async def create_product(api_client, name="Keyboard", stock=5, price=25):
    response = await api_client.post(
        "/products/", json={"name": name, "stock": stock, "price": price}
    )
    assert response.status_code == 200
    return response.json()


async def test_product_crud_round_trip(api_client):
    product = await create_product(api_client)

    fetched = await api_client.get(f"/products/{product['id']}")
    assert fetched.status_code == 200
    assert fetched.json() == product

    listed = await api_client.get("/products/")
    assert [item["id"] for item in listed.json()] == [product["id"]]

    deleted = await api_client.delete(f"/products/{product['id']}")
    assert deleted.status_code == 200
    assert deleted.json()["id"] == product["id"]

    assert (await api_client.get(f"/products/{product['id']}")).status_code == 404


async def test_duplicate_name_is_rejected(api_client):
    await create_product(api_client, name="Keyboard")

    conflict = await api_client.post(
        "/products/", json={"name": "Keyboard", "stock": 1, "price": 1}
    )

    assert conflict.status_code == 409


async def test_cache_ttl_endpoint_reports_a_live_ttl(api_client, fake_adapters):
    product = await create_product(api_client)

    response = await api_client.get(f"/products/cache/{product['id']}/ttl")

    assert response.status_code == 200
    assert response.json() == fake_adapters.product_cache.ttl_seconds


async def test_cache_ttl_is_unavailable_without_redis(api_client_without_redis):
    await create_product(api_client_without_redis)

    response = await api_client_without_redis.get("/products/cache/1/ttl")

    assert response.status_code == 503


async def test_products_still_work_without_redis(api_client_without_redis):
    product = await create_product(api_client_without_redis, name="Offline")

    fetched = await api_client_without_redis.get(f"/products/{product['id']}")

    assert fetched.status_code == 200
    assert fetched.json()["name"] == "Offline"


async def test_unknown_product_returns_404(api_client):
    assert (await api_client.get("/products/4242")).status_code == 404
    assert (await api_client.delete("/products/4242")).status_code == 404


async def test_invalid_product_payload_is_rejected(api_client):
    response = await api_client.post(
        "/products/", json={"name": "Bad", "stock": "many", "price": 1}
    )

    assert response.status_code == 422
