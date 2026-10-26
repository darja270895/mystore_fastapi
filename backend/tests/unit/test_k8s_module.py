"""Unit tests for the Kubernetes base functionality module (service, probes, HTTP K8s API client)."""

from __future__ import annotations

import json
import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from backend.k8s.k8s_adapters import (
    KubernetesHttpClusterAdapter,
    RuntimeDependencyHealthAdapter,
    SimulatedK8sClusterAdapter,
)
from backend.k8s.k8s_schemas import ScaleDeploymentRequest, TriggerJobRequest
from backend.k8s.k8s_service import K8sService


async def test_readiness_returns_ok_when_db_and_redis_are_healthy(db_session: AsyncSession):
    async def healthy_redis() -> bool:
        return True

    checker = RuntimeDependencyHealthAdapter(
        db_session=db_session,
        redis_ping=healthy_redis,
        redis_enabled=True,
        startup_complete=True,
        stream_consumer_active=True,
    )
    service = K8sService(
        health_checker=checker,
        cluster_gateway=SimulatedK8sClusterAdapter(),
    )

    ready, report = await service.check_readiness()

    assert ready is True
    assert report.status == "ok"
    assert {c.name: c.status for c in report.components} == {
        "database": "up",
        "redis": "up",
    }


async def test_readiness_degrades_when_redis_is_unreachable(db_session: AsyncSession):
    async def failing_redis() -> bool:
        raise ConnectionError("Redis connection refused")

    checker = RuntimeDependencyHealthAdapter(
        db_session=db_session,
        redis_ping=failing_redis,
        redis_enabled=True,
    )
    service = K8sService(
        health_checker=checker,
        cluster_gateway=SimulatedK8sClusterAdapter(),
    )

    ready, report = await service.check_readiness()

    assert ready is False
    assert report.status == "degraded"
    redis_component = next(c for c in report.components if c.name == "redis")
    assert redis_component.status == "down"
    assert "Redis connection refused" in (redis_component.detail or "")


async def test_kubernetes_http_adapter_talks_to_k8s_rest_api():
    """Verify real Kubernetes REST API paths and payloads via httpx.MockTransport."""

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if request.method == "GET" and path == "/api/v1/namespaces/mystore/pods":
            return httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "metadata": {"name": "mystore-api-abc", "namespace": "mystore"},
                            "spec": {"nodeName": "node-1"},
                            "status": {
                                "phase": "Running",
                                "podIP": "10.244.0.15",
                                "containerStatuses": [{"ready": True, "restartCount": 1}],
                            },
                        }
                    ]
                },
            )
        if (
            request.method == "GET"
            and path == "/apis/apps/v1/namespaces/mystore/deployments/mystore-api"
        ):
            return httpx.Response(
                200,
                json={
                    "spec": {"replicas": 2},
                    "status": {"readyReplicas": 2, "availableReplicas": 2},
                },
            )
        if (
            request.method == "PATCH"
            and path == "/apis/apps/v1/namespaces/mystore/deployments/mystore-api/scale"
        ):
            body = json.loads(request.content.decode())
            assert body == {"spec": {"replicas": 4}}
            return httpx.Response(200, json={"spec": {"replicas": 4}})
        if (
            request.method == "GET"
            and path
            == "/apis/coordination.k8s.io/v1/namespaces/mystore/leases/mystore-lease"
        ):
            return httpx.Response(404, json={"message": "not found"})
        if (
            request.method == "POST"
            and path == "/apis/coordination.k8s.io/v1/namespaces/mystore/leases"
        ):
            return httpx.Response(201, json={"metadata": {"name": "mystore-lease"}})
        if request.method == "POST" and path == "/apis/batch/v1/namespaces/mystore/jobs":
            return httpx.Response(201, json={"metadata": {"name": "created-job"}})

        return httpx.Response(404)

    adapter = KubernetesHttpClusterAdapter(
        api_server="https://kubernetes.default.svc",
        bearer_token="test-sa-token",
        mode="in-cluster",
        transport=httpx.MockTransport(handler),
    )

    pods = await adapter.list_pods("mystore")
    assert len(pods) == 1
    assert pods[0].name == "mystore-api-abc"
    assert pods[0].ready is True
    assert pods[0].restarts == 1

    scaled = await adapter.scale_deployment("mystore", "mystore-api", 4)
    assert scaled.previous_replicas == 2
    assert scaled.desired_replicas == 4
    assert scaled.mode == "in-cluster"

    lease = await adapter.acquire_or_renew_lease(
        namespace="mystore",
        lease_name="mystore-lease",
        holder_identity="mystore-api-abc",
        duration_seconds=30,
    )
    assert lease.acquired is True
    assert lease.holder_identity == "mystore-lease" or lease.holder_identity == "mystore-api-abc"

    job = await adapter.trigger_job("mystore", "stock-reconciliation", dry_run=False)
    assert job.status == "created"
    assert job.job_kind == "stock-reconciliation"


async def test_simulated_cluster_adapter_scales_and_triggers_jobs(db_session: AsyncSession):
    sim = SimulatedK8sClusterAdapter()
    checker = RuntimeDependencyHealthAdapter(db_session=db_session, redis_enabled=False)
    service = K8sService(health_checker=checker, cluster_gateway=sim)

    scale_res = await service.scale_deployment(
        ScaleDeploymentRequest(deployment_name="mystore-api", replicas=3)
    )
    assert scale_res.desired_replicas == 3

    pods = await service.list_namespace_pods()
    assert len(pods) == 3

    job_res = await service.trigger_job(
        TriggerJobRequest(job_kind="cache-warmup", dry_run=True)
    )
    assert job_res.job_kind == "cache-warmup"
    assert job_res.status == "simulated"
