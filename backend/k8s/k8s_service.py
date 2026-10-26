"""Application service for Kubernetes probes, Downward API introspection, and cluster operations."""

from __future__ import annotations

from datetime import datetime, timezone
import os
import platform
import time

from backend.config import settings
from backend.k8s.k8s_adapters import resolve_pod_environment
from backend.k8s.k8s_ports import DependencyHealthChecker, K8sClusterGateway
from backend.k8s.k8s_schemas import (
    ClusterOverviewResponse,
    ComponentHealth,
    LeaseStatusResponse,
    PodIdentityResponse,
    PodSummary,
    ProbeResponse,
    ScaleDeploymentRequest,
    ScaleDeploymentResponse,
    TriggerJobRequest,
    TriggerJobResponse,
)

_PROCESS_START_MONOTONIC = time.monotonic()


class K8sService:
    """Use-case service connecting MyStore FastAPI with Kubernetes runtime & API."""

    def __init__(
        self,
        health_checker: DependencyHealthChecker,
        cluster_gateway: K8sClusterGateway,
    ) -> None:
        self._health = health_checker
        self._cluster = cluster_gateway

    def get_pod_identity(self) -> PodIdentityResponse:
        env = resolve_pod_environment()
        uptime = round(max(0.0, time.monotonic() - _PROCESS_START_MONOTONIC), 2)
        return PodIdentityResponse(
            pod_name=env["pod_name"],
            pod_namespace=env["pod_namespace"],
            pod_ip=env["pod_ip"],
            node_name=env["node_name"],
            service_account=env["service_account"],
            deployment_name=env["deployment_name"],
            in_cluster=env["in_cluster"],
            worker_pid=os.getpid(),
            python_version=platform.python_version(),
            uptime_seconds=uptime,
            stream_consumer_active=self._health.is_stream_consumer_active(),
        )

    async def check_liveness(self) -> ProbeResponse:
        """Liveness probe: confirms the Python asyncio worker process is responsive."""
        pod = self.get_pod_identity()
        return ProbeResponse(
            probe="liveness",
            status="ok",
            pod_name=pod.pod_name,
            worker_pid=pod.worker_pid,
            timestamp=datetime.now(timezone.utc),
            components=[
                ComponentHealth(
                    name="asyncio_event_loop",
                    status="up",
                    latency_ms=0.0,
                    detail=f"Python {pod.python_version} worker PID {pod.worker_pid}",
                )
            ],
        )

    async def check_startup(self) -> tuple[bool, ProbeResponse]:
        """Startup probe: verifies application lifespan initialization finished."""
        pod = self.get_pod_identity()
        started = self._health.is_startup_complete()
        return (
            started,
            ProbeResponse(
                probe="startup",
                status="ok" if started else "starting",
                pod_name=pod.pod_name,
                worker_pid=pod.worker_pid,
                timestamp=datetime.now(timezone.utc),
                components=[
                    ComponentHealth(
                        name="lifespan_startup",
                        status="up" if started else "down",
                        latency_ms=0.0,
                        detail="Application lifespan initialized"
                        if started
                        else "Lifespan still initializing",
                    )
                ],
            ),
        )

    async def check_readiness(self) -> tuple[bool, ProbeResponse]:
        """Readiness probe: checks SQLite DB and Redis before Kubernetes routes traffic."""
        pod = self.get_pod_identity()
        db_health = await self._health.check_database()
        redis_health = await self._health.check_redis()
        components = [db_health, redis_health]

        ready = all(c.status in ("up", "disabled") for c in components)
        return (
            ready,
            ProbeResponse(
                probe="readiness",
                status="ok" if ready else "degraded",
                pod_name=pod.pod_name,
                worker_pid=pod.worker_pid,
                timestamp=datetime.now(timezone.utc),
                components=components,
            ),
        )

    async def get_cluster_overview(self) -> ClusterOverviewResponse:
        pod = self.get_pod_identity()
        pods = await self._cluster.list_pods(pod.pod_namespace)
        deployment = await self._cluster.get_deployment_status(
            pod.pod_namespace, pod.deployment_name
        )
        return ClusterOverviewResponse(
            mode=self._cluster.mode,
            api_server=self._cluster.api_server,
            namespace=pod.pod_namespace,
            current_pod=pod,
            deployment=deployment,
            pods=pods,
        )

    async def list_namespace_pods(self) -> list[PodSummary]:
        pod = self.get_pod_identity()
        return await self._cluster.list_pods(pod.pod_namespace)

    async def scale_deployment(
        self, request: ScaleDeploymentRequest
    ) -> ScaleDeploymentResponse:
        pod = self.get_pod_identity()
        return await self._cluster.scale_deployment(
            namespace=pod.pod_namespace,
            deployment_name=request.deployment_name,
            replicas=request.replicas,
        )

    async def acquire_leader_lease(self) -> LeaseStatusResponse:
        pod = self.get_pod_identity()
        return await self._cluster.acquire_or_renew_lease(
            namespace=pod.pod_namespace,
            lease_name=settings.K8S_LEASE_NAME,
            holder_identity=pod.pod_name,
            duration_seconds=settings.K8S_LEASE_DURATION_SECONDS,
        )

    async def get_leader_lease(self) -> LeaseStatusResponse:
        pod = self.get_pod_identity()
        return await self._cluster.get_lease(
            namespace=pod.pod_namespace,
            lease_name=settings.K8S_LEASE_NAME,
            duration_seconds=settings.K8S_LEASE_DURATION_SECONDS,
        )

    async def trigger_job(self, request: TriggerJobRequest) -> TriggerJobResponse:
        pod = self.get_pod_identity()
        return await self._cluster.trigger_job(
            namespace=pod.pod_namespace,
            job_kind=request.job_kind,
            dry_run=request.dry_run,
        )
