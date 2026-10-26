"""Application ports for Kubernetes health verification and cluster API operations."""

from __future__ import annotations

from typing import Literal, Protocol

from backend.k8s.k8s_schemas import (
    ComponentHealth,
    DeploymentStatus,
    LeaseStatusResponse,
    PodSummary,
    ScaleDeploymentResponse,
    TriggerJobResponse,
)


class DependencyHealthChecker(Protocol):
    """Port for verifying liveness/readiness of backing dependencies (SQLite/DB, Redis)."""

    async def check_database(self) -> ComponentHealth: ...

    async def check_redis(self) -> ComponentHealth: ...

    def is_startup_complete(self) -> bool: ...

    def is_stream_consumer_active(self) -> bool: ...


class K8sClusterGateway(Protocol):
    """Port for interacting with the Kubernetes API Server (in-cluster or simulated)."""

    @property
    def mode(self) -> Literal["in-cluster", "remote-api", "local-simulated"]: ...

    @property
    def api_server(self) -> str: ...

    async def list_pods(self, namespace: str) -> list[PodSummary]: ...

    async def get_deployment_status(
        self, namespace: str, deployment_name: str
    ) -> DeploymentStatus: ...

    async def scale_deployment(
        self, namespace: str, deployment_name: str, replicas: int
    ) -> ScaleDeploymentResponse: ...

    async def acquire_or_renew_lease(
        self,
        namespace: str,
        lease_name: str,
        holder_identity: str,
        duration_seconds: int,
    ) -> LeaseStatusResponse: ...

    async def get_lease(
        self, namespace: str, lease_name: str, duration_seconds: int
    ) -> LeaseStatusResponse: ...

    async def trigger_job(
        self,
        namespace: str,
        job_kind: str,
        dry_run: bool = False,
    ) -> TriggerJobResponse: ...
