"""End-to-end HTTP tests for the /k8s router and Pod identity headers."""

from __future__ import annotations


async def test_pod_identity_headers_are_attached_to_responses(api_client, monkeypatch):
    monkeypatch.setenv("POD_NAME", "mystore-api-7f8b9c-x2k9p")
    monkeypatch.setenv("POD_NAMESPACE", "mystore-prod")

    response = await api_client.get("/k8s/pod")

    assert response.status_code == 200
    assert response.headers["x-k8s-pod-name"] == "mystore-api-7f8b9c-x2k9p"
    assert response.headers["x-k8s-namespace"] == "mystore-prod"
    assert "x-worker-pid" in response.headers

    body = response.json()
    assert body["pod_name"] == "mystore-api-7f8b9c-x2k9p"
    assert body["pod_namespace"] == "mystore-prod"
    assert body["python_version"].startswith("3.12")


async def test_kubernetes_probes_livez_startupz_readyz(api_client):
    livez = await api_client.get("/k8s/probes/livez")
    assert livez.status_code == 200
    assert livez.json()["status"] == "ok"

    startupz = await api_client.get("/k8s/probes/startupz")
    assert startupz.status_code == 200
    assert startupz.json()["status"] == "ok"

    readyz = await api_client.get("/k8s/probes/readyz")
    assert readyz.status_code == 200
    assert readyz.json()["status"] == "ok"


async def test_cluster_overview_scale_lease_and_jobs_endpoints(api_client):
    overview = await api_client.get("/k8s/cluster/overview")
    assert overview.status_code == 200
    assert overview.json()["mode"] == "local-simulated"

    scaled = await api_client.post(
        "/k8s/cluster/scale",
        json={"deployment_name": "mystore-api", "replicas": 3},
    )
    assert scaled.status_code == 200
    assert scaled.json()["desired_replicas"] == 3

    pods = await api_client.get("/k8s/cluster/pods")
    assert pods.status_code == 200
    assert len(pods.json()) == 3

    lease = await api_client.post("/k8s/cluster/lease/acquire")
    assert lease.status_code == 200
    assert lease.json()["acquired"] is True

    job = await api_client.post(
        "/k8s/cluster/jobs/trigger",
        json={"job_kind": "stock-reconciliation", "dry_run": True},
    )
    assert job.status_code == 201
    assert job.json()["job_kind"] == "stock-reconciliation"
