"""FastAPI router for Kubernetes probes, Downward API pod metadata, and cluster control."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status

from backend.dependencies import get_k8s_service
from backend.k8s.k8s_schemas import (
    ClusterOverviewResponse,
    LeaseStatusResponse,
    PodIdentityResponse,
    PodSummary,
    ProbeResponse,
    ScaleDeploymentRequest,
    ScaleDeploymentResponse,
    TriggerJobRequest,
    TriggerJobResponse,
)
from backend.k8s.k8s_service import K8sService

router = APIRouter(
    prefix="/k8s",
    tags=["Kubernetes"],
)


@router.get("/pod", response_model=PodIdentityResponse)
async def get_pod_identity(
    service: K8sService = Depends(get_k8s_service),
) -> PodIdentityResponse:
    """Return Downward API pod identity, Python 3.12 runtime info, and worker status."""
    return service.get_pod_identity()


@router.get("/probes/livez", response_model=ProbeResponse)
async def liveness_probe(
    service: K8sService = Depends(get_k8s_service),
) -> ProbeResponse:
    """Kubernetes livenessProbe endpoint: verifies the Python asyncio worker is alive."""
    return await service.check_liveness()


@router.get("/probes/startupz", response_model=ProbeResponse)
async def startup_probe(
    response: Response,
    service: K8sService = Depends(get_k8s_service),
) -> ProbeResponse:
    """Kubernetes startupProbe endpoint: returns 200 once lifespan startup finishes, else 503."""
    started, payload = await service.check_startup()
    if not started:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return payload


@router.get("/probes/readyz", response_model=ProbeResponse)
async def readiness_probe(
    response: Response,
    service: K8sService = Depends(get_k8s_service),
) -> ProbeResponse:
    """Kubernetes readinessProbe endpoint: checks SQLite and Redis health (503 if degraded)."""
    ready, payload = await service.check_readiness()
    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return payload


@router.get("/cluster/overview", response_model=ClusterOverviewResponse)
async def get_cluster_overview(
    service: K8sService = Depends(get_k8s_service),
) -> ClusterOverviewResponse:
    """Inspect Kubernetes cluster connection mode, deployment replica state, and running pods."""
    return await service.get_cluster_overview()


@router.get("/cluster/pods", response_model=list[PodSummary])
async def list_cluster_pods(
    service: K8sService = Depends(get_k8s_service),
) -> list[PodSummary]:
    """List pods in the current Kubernetes namespace."""
    return await service.list_namespace_pods()


@router.post("/cluster/scale", response_model=ScaleDeploymentResponse)
async def scale_deployment(
    request: ScaleDeploymentRequest,
    service: K8sService = Depends(get_k8s_service),
) -> ScaleDeploymentResponse:
    """Scale a Kubernetes Deployment via the apps/v1 Scale subresource."""
    return await service.scale_deployment(request)


@router.get("/cluster/lease", response_model=LeaseStatusResponse)
async def get_leader_lease(
    service: K8sService = Depends(get_k8s_service),
) -> LeaseStatusResponse:
    """Inspect the coordination.k8s.io/v1 Lease for background stream consumer leadership."""
    return await service.get_leader_lease()


@router.post("/cluster/lease/acquire", response_model=LeaseStatusResponse)
async def acquire_leader_lease(
    service: K8sService = Depends(get_k8s_service),
) -> LeaseStatusResponse:
    """Acquire or renew the coordination.k8s.io/v1 Lease for this Pod."""
    return await service.acquire_leader_lease()


@router.post(
    "/cluster/jobs/trigger",
    response_model=TriggerJobResponse,
    status_code=status.HTTP_201_CREATED,
)
async def trigger_k8s_job(
    request: TriggerJobRequest,
    service: K8sService = Depends(get_k8s_service),
) -> TriggerJobResponse:
    """Trigger an on-demand Kubernetes batch/v1 Job (stock audit, cache warmup, cart cleanup)."""
    return await service.trigger_job(request)
