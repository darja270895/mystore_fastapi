Your 1-Working-Day (8-Hour) Practical Learning Plan
Open the Kubernetes 1-Day Mastery Canvas to check off each block interactively:

**Hour 1 (09:00–10:00) — Control Plane, OCI Image & RBAC (k8s/00-namespace-rbac.yaml)**

Enable Kubernetes in Docker Desktop (Settings -> Kubernetes -> Enable Kubernetes).
Build the image and create the mystore namespace + RBAC:

docker build -t mystore-api:latest ./backend
kubectl apply -f k8s/00-namespace-rbac.yaml

**Hour 2 (10:00–11:00) — ConfigMaps, Secrets & Stateful Redis (k8s/01-config-secret.yaml, k8s/02-redis-statefulset.yaml)**

Deploy externalized configuration and the Redis StatefulSet with a 1Gi PersistentVolumeClaim:

kubectl apply -f k8s/01-config-secret.yaml
kubectl apply -f k8s/02-redis-statefulset.yaml
kubectl -n mystore rollout status statefulset/redis

**Hour 3 (11:00–12:00) — Zero-Race Migrations with Job & CronJob (k8s/03-jobs-and-cronjobs.yaml)**
Run alembic upgrade head in a one-shot Kubernetes Job and register the 15-minute CronJob:

kubectl apply -f k8s/03-jobs-and-cronjobs.yaml
kubectl -n mystore logs job/mystore-db-migrate

**Hour 4 (12:00–13:00) — Self-Healing Probes (backend/k8s/k8s_router.py)**
Inspect how /k8s/probes/startupz, /k8s/probes/livez, and /k8s/probes/readyz differentiate between a slow startup, a deadlocked process, and a temporary Redis outage.

**Hour 5 (14:00–15:00) — Multi-Replica Deployment & Downward API (k8s/04-api-deployment-hpa.yaml)**
Deploy mystore-api with 2 replicas exposed on NodePort 30080 and observe X-K8s-Pod-Name changing across requests:

kubectl apply -f k8s/04-api-deployment-hpa.yaml
curl.exe -i http://127.0.0.1:30080/k8s/pod

**Hour 6 (15:00–16:00) — In-Cluster Python K8s Client & Live Scaling (backend/k8s/k8s_adapters.py)**
Query GET /k8s/cluster/overview and scale the deployment from 2 to 4 replicas right from Swagger UI (http://127.0.0.1:30080/docs) via POST /k8s/cluster/scale.

**Hour 7 (16:00–17:00) — Distributed Leader Election (Lease) & On-Demand Jobs (backend/k8s/k8s_service.py)**
Test POST /k8s/cluster/lease/acquire and trigger a stock-reconciliation Kubernetes Job via POST /k8s/cluster/jobs/trigger.

**Hour 8 (17:00–18:00) — HPA v2, PDB, NetworkPolicy & Automated Tests**
Inspect kubectl -n mystore get hpa,pdb,networkpolicy and run the unit + E2E test suite for the Kubernetes module:

.\backend\.venv\Scripts\pytest.exe backend/tests/unit/test_k8s_module.py backend/tests/e2e/te