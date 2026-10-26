"""Infrastructure adapters for Kubernetes API interaction and runtime dependency health checks."""

from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
import socket
import ssl
import time
from typing import Any, Callable, Coroutine, Literal
from uuid import uuid4

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.k8s.k8s_schemas import (
    ComponentHealth,
    DeploymentStatus,
    LeaseStatusResponse,
    PodSummary,
    ScaleDeploymentResponse,
    TriggerJobResponse,
)

JOB_COMMANDS: dict[str, list[str]] = {
    "stock-reconciliation": [
        "python",
        "-c",
        "print('Reconciling SQLite product stock with purchase ledger...')",
    ],
    "cache-warmup": [
        "python",
        "-c",
        "print('Warming Redis product cache from SQLite...')",
    ],
    "expired-cart-cleanup": [
        "python",
        "-c",
        "print('Scanning and expiring stale Redis shopping carts...')",
    ],
}


def resolve_pod_environment() -> dict[str, Any]:
    """Read Downward API environment variables and in-cluster ServiceAccount files."""
    token_path = Path(settings.K8S_TOKEN_PATH)
    ns_path = Path(settings.K8S_NAMESPACE_PATH)
    in_cluster = bool(os.getenv("KUBERNETES_SERVICE_HOST")) and token_path.exists()

    pod_name = (
        os.getenv("POD_NAME")
        or os.getenv("HOSTNAME")
        or settings.POD_NAME
        or socket.gethostname()
    )
    namespace = os.getenv("POD_NAMESPACE")
    if not namespace and ns_path.exists():
        namespace = ns_path.read_text(encoding="utf-8").strip()
    namespace = namespace or settings.POD_NAMESPACE

    pod_ip = os.getenv("POD_IP") or settings.POD_IP
    node_name = os.getenv("NODE_NAME") or settings.NODE_NAME
    service_account = os.getenv("K8S_SERVICE_ACCOUNT") or settings.K8S_SERVICE_ACCOUNT
    deployment_name = os.getenv("K8S_DEPLOYMENT_NAME") or settings.K8S_DEPLOYMENT_NAME

    return {
        "pod_name": pod_name,
        "pod_namespace": namespace,
        "pod_ip": pod_ip,
        "node_name": node_name,
        "service_account": service_account,
        "deployment_name": deployment_name,
        "in_cluster": in_cluster,
    }


class RuntimeDependencyHealthAdapter:
    """Checks SQLite/SQLAlchemy and Redis availability for Kubernetes readiness probes."""

    def __init__(
        self,
        db_session: AsyncSession,
        redis_ping: Callable[[], Coroutine[Any, Any, Any]] | None = None,
        redis_enabled: bool = True,
        startup_complete: bool = True,
        stream_consumer_active: bool = False,
    ) -> None:
        self._db_session = db_session
        self._redis_ping = redis_ping
        self._redis_enabled = redis_enabled
        self._startup_complete = startup_complete
        self._stream_consumer_active = stream_consumer_active

    async def check_database(self) -> ComponentHealth:
        started = time.perf_counter()
        try:
            await self._db_session.execute(text("SELECT 1"))
            latency = round((time.perf_counter() - started) * 1000, 2)
            return ComponentHealth(
                name="database",
                status="up",
                latency_ms=latency,
                detail="SQLite WAL connection healthy",
            )
        except Exception as exc:
            latency = round((time.perf_counter() - started) * 1000, 2)
            return ComponentHealth(
                name="database",
                status="down",
                latency_ms=latency,
                detail=str(exc),
            )

    async def check_redis(self) -> ComponentHealth:
        if not self._redis_enabled:
            return ComponentHealth(
                name="redis",
                status="disabled",
                latency_ms=0.0,
                detail="USE_REDIS is disabled",
            )
        if self._redis_ping is None:
            return ComponentHealth(
                name="redis",
                status="down",
                latency_ms=0.0,
                detail="Redis client not initialized on app.state",
            )
        started = time.perf_counter()
        try:
            pong = await self._redis_ping()
            latency = round((time.perf_counter() - started) * 1000, 2)
            return ComponentHealth(
                name="redis",
                status="up" if pong else "down",
                latency_ms=latency,
                detail="PONG" if pong else "Ping returned falsy",
            )
        except Exception as exc:
            latency = round((time.perf_counter() - started) * 1000, 2)
            return ComponentHealth(
                name="redis",
                status="down",
                latency_ms=latency,
                detail=str(exc),
            )

    def is_startup_complete(self) -> bool:
        return self._startup_complete

    def is_stream_consumer_active(self) -> bool:
        return self._stream_consumer_active


class SimulatedK8sClusterAdapter:
    """In-memory Kubernetes cluster simulator for local Docker/Windows development & testing.

    Provides realistic Kubernetes API responses when the app is running outside a
    real K8s cluster, so every endpoint (/k8s/cluster/*) can be practiced locally.
    """

    def __init__(self) -> None:
        env = resolve_pod_environment()
        self._pod_name: str = env["pod_name"]
        self._namespace: str = env["pod_namespace"]
        self._pod_ip: str = env["pod_ip"]
        self._node_name: str = env["node_name"]
        self._deployment_name: str = env["deployment_name"]
        self._replicas: int = 1
        self._lease_holder: str | None = self._pod_name
        self._lease_renew_time: datetime = datetime.now(timezone.utc)

    @property
    def mode(self) -> Literal["in-cluster", "remote-api", "local-simulated"]:
        return "local-simulated"

    @property
    def api_server(self) -> str:
        return "https://kubernetes.default.svc (simulated)"

    async def list_pods(self, namespace: str) -> list[PodSummary]:
        pods: list[PodSummary] = [
            PodSummary(
                name=self._pod_name,
                namespace=namespace,
                phase="Running",
                pod_ip=self._pod_ip,
                node_name=self._node_name,
                ready=True,
                restarts=0,
            )
        ]
        for idx in range(2, self._replicas + 1):
            pods.append(
                PodSummary(
                    name=f"{self._deployment_name}-replica-{idx}",
                    namespace=namespace,
                    phase="Running",
                    pod_ip=f"10.244.0.{10 + idx}",
                    node_name=self._node_name,
                    ready=True,
                    restarts=0,
                )
            )
        return pods

    async def get_deployment_status(
        self, namespace: str, deployment_name: str
    ) -> DeploymentStatus:
        return DeploymentStatus(
            name=deployment_name,
            namespace=namespace,
            desired_replicas=self._replicas,
            ready_replicas=self._replicas,
            available_replicas=self._replicas,
        )

    async def scale_deployment(
        self, namespace: str, deployment_name: str, replicas: int
    ) -> ScaleDeploymentResponse:
        prev = self._replicas
        self._replicas = replicas
        return ScaleDeploymentResponse(
            mode=self.mode,
            deployment_name=deployment_name,
            namespace=namespace,
            previous_replicas=prev,
            desired_replicas=replicas,
        )

    async def acquire_or_renew_lease(
        self,
        namespace: str,
        lease_name: str,
        holder_identity: str,
        duration_seconds: int,
    ) -> LeaseStatusResponse:
        now = datetime.now(timezone.utc)
        elapsed = (now - self._lease_renew_time).total_seconds()
        if (
            self._lease_holder is None
            or self._lease_holder == holder_identity
            or elapsed >= duration_seconds
        ):
            self._lease_holder = holder_identity
            self._lease_renew_time = now
            acquired = True
        else:
            acquired = False

        return LeaseStatusResponse(
            lease_name=lease_name,
            namespace=namespace,
            holder_identity=self._lease_holder,
            lease_duration_seconds=duration_seconds,
            acquired=acquired,
            renew_time=self._lease_renew_time,
        )

    async def get_lease(
        self, namespace: str, lease_name: str, duration_seconds: int
    ) -> LeaseStatusResponse:
        return LeaseStatusResponse(
            lease_name=lease_name,
            namespace=namespace,
            holder_identity=self._lease_holder,
            lease_duration_seconds=duration_seconds,
            acquired=self._lease_holder == self._pod_name,
            renew_time=self._lease_renew_time,
        )

    async def trigger_job(
        self,
        namespace: str,
        job_kind: str,
        dry_run: bool = False,
    ) -> TriggerJobResponse:
        suffix = uuid4().hex[:6]
        job_name = f"mystore-{job_kind}-{suffix}"
        command = JOB_COMMANDS.get(job_kind, ["python", "-m", "backend.main"])
        return TriggerJobResponse(
            mode=self.mode,
            job_name=job_name,
            namespace=namespace,
            job_kind=job_kind,
            status="simulated",
            command=command,
        )


class KubernetesHttpClusterAdapter:
    """Async httpx client for the real Kubernetes API Server (in-cluster or remote).

    Uses ServiceAccount bearer token authentication (/var/run/secrets/kubernetes.io/serviceaccount/token)
    or explicit K8S_API_SERVER + K8S_BEARER_TOKEN settings.
    """

    def __init__(
        self,
        api_server: str,
        bearer_token: str = "",
        ca_cert_path: str | None = None,
        mode: Literal["in-cluster", "remote-api"] = "in-cluster",
        timeout_s: float = 5.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._api_server = api_server.rstrip("/")
        self._bearer_token = bearer_token
        self._ca_cert_path = ca_cert_path
        self._mode: Literal["in-cluster", "remote-api"] = mode
        self._timeout_s = timeout_s
        self._transport = transport

    @property
    def mode(self) -> Literal["in-cluster", "remote-api", "local-simulated"]:
        return self._mode

    @property
    def api_server(self) -> str:
        return self._api_server

    def _client(self) -> httpx.AsyncClient:
        headers: dict[str, str] = {"Accept": "application/json"}
        if self._bearer_token:
            headers["Authorization"] = f"Bearer {self._bearer_token}"

        verify: bool | ssl.SSLContext = False
        if self._ca_cert_path and Path(self._ca_cert_path).exists():
            verify = ssl.create_default_context(cafile=self._ca_cert_path)

        return httpx.AsyncClient(
            base_url=self._api_server,
            headers=headers,
            verify=verify,
            timeout=self._timeout_s,
            transport=self._transport,
        )

    async def list_pods(self, namespace: str) -> list[PodSummary]:
        async with self._client() as client:
            resp = await client.get(f"/api/v1/namespaces/{namespace}/pods")
            resp.raise_for_status()
            payload = resp.json()

        pods: list[PodSummary] = []
        for item in payload.get("items", []):
            metadata = item.get("metadata", {})
            spec = item.get("spec", {})
            status = item.get("status", {})
            container_statuses = status.get("containerStatuses", []) or []
            ready = bool(container_statuses) and all(
                cs.get("ready", False) for cs in container_statuses
            )
            restarts = sum(int(cs.get("restartCount", 0)) for cs in container_statuses)
            pods.append(
                PodSummary(
                    name=metadata.get("name", "unknown"),
                    namespace=metadata.get("namespace", namespace),
                    phase=status.get("phase", "Unknown"),
                    pod_ip=status.get("podIP"),
                    node_name=spec.get("nodeName"),
                    ready=ready,
                    restarts=restarts,
                )
            )
        return pods

    async def get_deployment_status(
        self, namespace: str, deployment_name: str
    ) -> DeploymentStatus:
        async with self._client() as client:
            resp = await client.get(
                f"/apis/apps/v1/namespaces/{namespace}/deployments/{deployment_name}"
            )
            resp.raise_for_status()
            data = resp.json()

        spec_replicas = int(data.get("spec", {}).get("replicas", 1))
        status = data.get("status", {})
        return DeploymentStatus(
            name=deployment_name,
            namespace=namespace,
            desired_replicas=spec_replicas,
            ready_replicas=int(status.get("readyReplicas", 0)),
            available_replicas=int(status.get("availableReplicas", 0)),
        )

    async def scale_deployment(
        self, namespace: str, deployment_name: str, replicas: int
    ) -> ScaleDeploymentResponse:
        current = await self.get_deployment_status(namespace, deployment_name)
        patch_body = {"spec": {"replicas": replicas}}
        async with self._client() as client:
            resp = await client.patch(
                f"/apis/apps/v1/namespaces/{namespace}/deployments/{deployment_name}/scale",
                json=patch_body,
                headers={"Content-Type": "application/merge-patch+json"},
            )
            resp.raise_for_status()

        return ScaleDeploymentResponse(
            mode=self.mode,
            deployment_name=deployment_name,
            namespace=namespace,
            previous_replicas=current.desired_replicas,
            desired_replicas=replicas,
        )

    async def acquire_or_renew_lease(
        self,
        namespace: str,
        lease_name: str,
        holder_identity: str,
        duration_seconds: int,
    ) -> LeaseStatusResponse:
        now = datetime.now(timezone.utc)
        micro_time = now.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        lease_manifest = {
            "apiVersion": "coordination.k8s.io/v1",
            "kind": "Lease",
            "metadata": {"name": lease_name, "namespace": namespace},
            "spec": {
                "holderIdentity": holder_identity,
                "leaseDurationSeconds": duration_seconds,
                "renewTime": micro_time,
            },
        }
        async with self._client() as client:
            get_resp = await client.get(
                f"/apis/coordination.k8s.io/v1/namespaces/{namespace}/leases/{lease_name}"
            )
            if get_resp.status_code == 404:
                create_resp = await client.post(
                    f"/apis/coordination.k8s.io/v1/namespaces/{namespace}/leases",
                    json=lease_manifest,
                )
                create_resp.raise_for_status()
                return LeaseStatusResponse(
                    lease_name=lease_name,
                    namespace=namespace,
                    holder_identity=holder_identity,
                    lease_duration_seconds=duration_seconds,
                    acquired=True,
                    renew_time=now,
                )

            get_resp.raise_for_status()
            existing = get_resp.json()
            spec = existing.get("spec", {})
            current_holder = spec.get("holderIdentity")

            if current_holder in (None, "", holder_identity):
                patch_resp = await client.patch(
                    f"/apis/coordination.k8s.io/v1/namespaces/{namespace}/leases/{lease_name}",
                    json={"spec": lease_manifest["spec"]},
                    headers={"Content-Type": "application/merge-patch+json"},
                )
                patch_resp.raise_for_status()
                return LeaseStatusResponse(
                    lease_name=lease_name,
                    namespace=namespace,
                    holder_identity=holder_identity,
                    lease_duration_seconds=duration_seconds,
                    acquired=True,
                    renew_time=now,
                )

            return LeaseStatusResponse(
                lease_name=lease_name,
                namespace=namespace,
                holder_identity=current_holder,
                lease_duration_seconds=int(
                    spec.get("leaseDurationSeconds", duration_seconds)
                ),
                acquired=False,
                renew_time=now,
            )

    async def get_lease(
        self, namespace: str, lease_name: str, duration_seconds: int
    ) -> LeaseStatusResponse:
        now = datetime.now(timezone.utc)
        env = resolve_pod_environment()
        async with self._client() as client:
            resp = await client.get(
                f"/apis/coordination.k8s.io/v1/namespaces/{namespace}/leases/{lease_name}"
            )
            if resp.status_code == 404:
                return LeaseStatusResponse(
                    lease_name=lease_name,
                    namespace=namespace,
                    holder_identity=None,
                    lease_duration_seconds=duration_seconds,
                    acquired=False,
                    renew_time=now,
                )
            resp.raise_for_status()
            spec = resp.json().get("spec", {})
            holder = spec.get("holderIdentity")
            return LeaseStatusResponse(
                lease_name=lease_name,
                namespace=namespace,
                holder_identity=holder,
                lease_duration_seconds=int(
                    spec.get("leaseDurationSeconds", duration_seconds)
                ),
                acquired=holder == env["pod_name"],
                renew_time=now,
            )

    async def trigger_job(
        self,
        namespace: str,
        job_kind: str,
        dry_run: bool = False,
    ) -> TriggerJobResponse:
        suffix = uuid4().hex[:6]
        job_name = f"mystore-{job_kind}-{suffix}"
        command = JOB_COMMANDS.get(job_kind, ["python", "-m", "backend.main"])
        if dry_run:
            return TriggerJobResponse(
                mode=self.mode,
                job_name=job_name,
                namespace=namespace,
                job_kind=job_kind,
                status="simulated",
                command=command,
            )

        job_manifest = {
            "apiVersion": "batch/v1",
            "kind": "Job",
            "metadata": {
                "name": job_name,
                "namespace": namespace,
                "labels": {"app": "mystore-api", "job-kind": job_kind},
            },
            "spec": {
                "ttlSecondsAfterFinished": 300,
                "backoffLimit": 2,
                "template": {
                    "spec": {
                        "restartPolicy": "Never",
                        "containers": [
                            {
                                "name": job_kind,
                                "image": settings.K8S_JOB_IMAGE,
                                "imagePullPolicy": "IfNotPresent",
                                "command": command,
                            }
                        ],
                    }
                },
            },
        }
        async with self._client() as client:
            resp = await client.post(
                f"/apis/batch/v1/namespaces/{namespace}/jobs",
                json=job_manifest,
            )
            resp.raise_for_status()

        return TriggerJobResponse(
            mode=self.mode,
            job_name=job_name,
            namespace=namespace,
            job_kind=job_kind,
            status="created",
            command=command,
        )


_SIMULATED_SINGLETON = SimulatedK8sClusterAdapter()


def build_k8s_cluster_gateway() -> KubernetesHttpClusterAdapter | SimulatedK8sClusterAdapter:
    """Auto-detect In-Cluster Kubernetes API, configured remote API, or local simulation."""
    host = os.getenv("KUBERNETES_SERVICE_HOST")
    port = os.getenv("KUBERNETES_SERVICE_PORT_HTTPS", "443")
    token_path = Path(settings.K8S_TOKEN_PATH)

    if host and token_path.exists():
        token = token_path.read_text(encoding="utf-8").strip()
        return KubernetesHttpClusterAdapter(
            api_server=f"https://{host}:{port}",
            bearer_token=token,
            ca_cert_path=settings.K8S_CA_CERT_PATH,
            mode="in-cluster",
            timeout_s=settings.K8S_API_TIMEOUT_SECONDS,
        )

    if settings.K8S_API_SERVER:
        return KubernetesHttpClusterAdapter(
            api_server=settings.K8S_API_SERVER,
            bearer_token=settings.K8S_BEARER_TOKEN,
            ca_cert_path=settings.K8S_CA_CERT_PATH,
            mode="remote-api",
            timeout_s=settings.K8S_API_TIMEOUT_SECONDS,
        )

    return _SIMULATED_SINGLETON
