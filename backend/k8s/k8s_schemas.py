"""Pydantic schemas for Kubernetes probes, Downward API pod metadata, and cluster operations."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class PodIdentityResponse(BaseModel):
    """Pod and runtime metadata populated via the Kubernetes Downward API."""

    pod_name: str
    pod_namespace: str
    pod_ip: str
    node_name: str
    service_account: str
    deployment_name: str
    in_cluster: bool
    worker_pid: int
    python_version: str
    uptime_seconds: float
    stream_consumer_active: bool


class ComponentHealth(BaseModel):
    """Health check result for an individual infrastructure dependency."""

    name: str
    status: Literal["up", "down", "disabled"]
    latency_ms: float | None = None
    detail: str | None = None


class ProbeResponse(BaseModel):
    """Standardized payload for /k8s/probes/{livez,readyz,startupz}."""

    probe: Literal["liveness", "readiness", "startup"]
    status: Literal["ok", "degraded", "starting"]
    pod_name: str
    worker_pid: int
    timestamp: datetime
    components: list[ComponentHealth] = Field(default_factory=list)


class PodSummary(BaseModel):
    """Summary of a Kubernetes Pod returned by the Cluster API."""

    name: str
    namespace: str
    phase: str
    pod_ip: str | None = None
    node_name: str | None = None
    ready: bool = False
    restarts: int = 0


class DeploymentStatus(BaseModel):
    """Replica state of a Kubernetes Deployment."""

    name: str
    namespace: str
    desired_replicas: int
    ready_replicas: int
    available_replicas: int


class ClusterOverviewResponse(BaseModel):
    """Aggregated view of the Kubernetes cluster connection and workload state."""

    mode: Literal["in-cluster", "remote-api", "local-simulated"]
    api_server: str
    namespace: str
    current_pod: PodIdentityResponse
    deployment: DeploymentStatus
    pods: list[PodSummary]


class ScaleDeploymentRequest(BaseModel):
    """Request payload to scale a Kubernetes Deployment."""

    deployment_name: str = Field(default="mystore-api", min_length=1)
    replicas: int = Field(ge=1, le=20, description="Desired number of Pod replicas")


class ScaleDeploymentResponse(BaseModel):
    """Result of scaling a Kubernetes Deployment."""

    mode: Literal["in-cluster", "remote-api", "local-simulated"]
    deployment_name: str
    namespace: str
    previous_replicas: int
    desired_replicas: int


class LeaseStatusResponse(BaseModel):
    """State of a coordination.k8s.io/v1 Lease used for leader election."""

    lease_name: str
    namespace: str
    holder_identity: str | None
    lease_duration_seconds: int
    acquired: bool
    renew_time: datetime


class TriggerJobRequest(BaseModel):
    """Request payload to spawn a Kubernetes batch/v1 Job from the API."""

    job_kind: Literal["stock-reconciliation", "cache-warmup", "expired-cart-cleanup"]
    dry_run: bool = False


class TriggerJobResponse(BaseModel):
    """Metadata of the created Kubernetes batch/v1 Job."""

    mode: Literal["in-cluster", "remote-api", "local-simulated"]
    job_name: str
    namespace: str
    job_kind: str
    status: Literal["created", "simulated"]
    command: list[str]
