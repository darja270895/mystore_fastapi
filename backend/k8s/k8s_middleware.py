"""ASGI middleware that stamps every HTTP response with Kubernetes Pod and Worker headers."""

from __future__ import annotations

import os
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from backend.k8s.k8s_adapters import resolve_pod_environment


class K8sPodIdentityMiddleware(BaseHTTPMiddleware):
    """Injects X-K8s-Pod-Name, X-K8s-Namespace, and X-Worker-Pid headers 
    for replica observability so you can watch Kubernetes load-balance requests across pods."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        env = resolve_pod_environment()
        response.headers["X-K8s-Pod-Name"] = env["pod_name"]
        response.headers["X-K8s-Namespace"] = env["pod_namespace"]
        response.headers["X-Worker-Pid"] = str(os.getpid())
        return response
