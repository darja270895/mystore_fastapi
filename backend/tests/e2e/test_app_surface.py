"""Application-level end-to-end checks: root page, docs, CORS, route table."""


async def test_root_serves_the_frontend_or_a_fallback(api_client):
    response = await api_client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"] or response.json()


async def test_openapi_schema_lists_every_feature_route(api_client):
    response = await api_client.get("/openapi.json")

    paths = response.json()["paths"]
    for route in (
        "/users/",
        "/users/{user_id}",
        "/products/",
        "/products/{product_id}",
        "/products/cache/{product_id}/ttl",
        "/purchases/",
        "/purchases/recent",
        "/purchases/stock-movements",
        "/purchases/notifications/{user_id}",
        "/card/add",
        "/card/remove",
        "/card/clear/{user_id}",
        "/card/checkout/{user_id}",
        "/card/events/live",
        "/card/{user_id}",
        "/k8s/pod",
        "/k8s/probes/livez",
        "/k8s/probes/startupz",
        "/k8s/probes/readyz",
        "/k8s/cluster/overview",
        "/k8s/cluster/pods",
        "/k8s/cluster/scale",
        "/k8s/cluster/lease",
        "/k8s/cluster/lease/acquire",
        "/k8s/cluster/jobs/trigger",
    ):
        assert route in paths


async def test_cors_headers_are_returned_for_the_dev_frontend(api_client):
    response = await api_client.get("/users/", headers={"Origin": "http://localhost:5173"})

    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


async def test_unknown_route_returns_404(api_client):
    assert (await api_client.get("/nope")).status_code == 404
