<#
.SYNOPSIS
  Build images and deploy MyStore (3 API pods, 1 login pod, 3 frontend pods, Redis) to a local cluster.

.EXAMPLE
  .\k8s\deploy.ps1              # build + deploy
  .\k8s\deploy.ps1 -SkipBuild   # re-apply manifests only
  .\k8s\deploy.ps1 -Delete      # remove everything (namespace + volumes)
#>
param(
    [switch]$SkipBuild,
    [switch]$Delete
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$K8sDir = $PSScriptRoot
$Namespace = "mystore"

function Invoke-Checked {
    param([string]$Command, [string[]]$Arguments)
    & $Command @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Command $($Arguments -join ' ') failed with exit code $LASTEXITCODE" }
}

if ($Delete) {
    Invoke-Checked kubectl @("delete", "namespace", $Namespace, "--ignore-not-found")
    return
}

$context = (kubectl config current-context).Trim()
Write-Host "==> kubectl context: $context"

if (-not $SkipBuild) {
    Write-Host "==> Building mystore-api:local"
    Invoke-Checked docker @("build", "-t", "mystore-api:local", (Join-Path $RepoRoot "backend"))

    Write-Host "==> Building mystore-login:local"
    Invoke-Checked docker @("build", "-t", "mystore-login:local", (Join-Path $RepoRoot "backend\login_service"))

    Write-Host "==> Building mystore-frontend:local"
    Invoke-Checked docker @("build", "-t", "mystore-frontend:local", (Join-Path $RepoRoot "frontend"))

    # kind and minikube run their own container runtime and don't see the host's Docker images.
    if ($context -like "kind-*") {
        $cluster = $context.Substring(5)
        Invoke-Checked kind @("load", "docker-image", "mystore-api:local", "mystore-login:local", "mystore-frontend:local", "--name", $cluster)
    }
    elseif ($context -eq "minikube") {
        Invoke-Checked minikube @("image", "load", "mystore-api:local")
        Invoke-Checked minikube @("image", "load", "mystore-login:local")
        Invoke-Checked minikube @("image", "load", "mystore-frontend:local")
    }
}

# A finished Job can't be updated in place; recreate it so migrations run against the new image.
kubectl -n $Namespace delete job mystore-db-migrate --ignore-not-found 2>$null | Out-Null

Write-Host "==> Applying manifests"
Invoke-Checked kubectl @("apply", "-k", $K8sDir)

Write-Host "==> Waiting for Redis"
Invoke-Checked kubectl @("-n", $Namespace, "rollout", "status", "statefulset/redis", "--timeout=180s")

Write-Host "==> Waiting for database migration Job"
Invoke-Checked kubectl @("-n", $Namespace, "wait", "--for=condition=complete", "job/mystore-db-migrate", "--timeout=180s")

# The image tag ("local") never changes and ConfigMap edits don't reach running pods,
# so force fresh pods on every deploy.
Write-Host "==> Restarting deployments"
Invoke-Checked kubectl @("-n", $Namespace, "rollout", "restart", "deployment/mystore-api", "deployment/mystore-login", "deployment/mystore-frontend")

Write-Host "==> Waiting for login service (1 pod)"
Invoke-Checked kubectl @("-n", $Namespace, "rollout", "status", "deployment/mystore-login", "--timeout=300s")

Write-Host "==> Waiting for API (3 pods)"
Invoke-Checked kubectl @("-n", $Namespace, "rollout", "status", "deployment/mystore-api", "--timeout=300s")

Write-Host "==> Waiting for frontend (3 pods)"
Invoke-Checked kubectl @("-n", $Namespace, "rollout", "status", "deployment/mystore-frontend", "--timeout=180s")

kubectl -n $Namespace get pods -o wide

Write-Host ""
Write-Host "Frontend : http://localhost:30080"
Write-Host "API docs : http://localhost:30800/docs"
Write-Host "Pod info : http://localhost:30800/k8s/pod   (repeat to see different pods answer)"
Write-Host "Login API: http://localhost:30801/docs"
if ($context -like "kind-*" -or $context -eq "minikube") {
    Write-Host ""
    Write-Host "NodePorts may not be reachable on localhost for $context. Use port-forward instead:"
    Write-Host "  kubectl -n $Namespace port-forward svc/mystore-frontend 30080:80"
    Write-Host "  kubectl -n $Namespace port-forward svc/mystore-api 30800:8000"
    Write-Host "  kubectl -n $Namespace port-forward svc/mystore-login 30801:8001"
}
