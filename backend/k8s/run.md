**How to run it**
1. In Docker Desktop, go to Settings → Kubernetes → Enable Kubernetes, and wait until it shows as running.
2. From the repo root, run .\k8s\deploy.ps1.
3. Open the store at http://localhost:30080 and the API docs at http://localhost:30800/docs.

To check that load balancing works, call http://localhost:30800/k8s/pod several times. The pod name changes as different backend pods answer. To remove everything, run .\k8s\deploy.ps1 -Delete.

***How a request flows***

Browser ──► localhost:30080 ──► Service mystore-frontend ──► 1 of 3 nginx pods
                                                               │  /api/* is proxied
                                                               ▼
                                          Service mystore-api ──► 1 of 3 FastAPI pods
                                                                   │            │
                                                     Redis (StatefulSet)   SQLite file on a shared volume


The browser only talks to nginx. Nginx serves the React files and forwards /api/... to the backend Service. Because everything comes from the same origin, no CORS change was needed in main.py.

**Files in k8s/**
- kustomization.yaml: lists every manifest and puts them all in the mystore namespace, so kubectl apply -k k8s deploys the whole stack.
- 00-namespace.yaml: creates the mystore namespace. Everything lives there, and deleting it cleans up completely.
- 01-rbac.yaml: creates a ServiceAccount for the backend pods, a Role allowing them to read pods, scale the deployment, and manage Leases and Jobs, plus a RoleBinding that grants it. Your /k8s/cluster/* endpoints need this to call the real Kubernetes API from inside a pod.
- 02-config.yaml: a ConfigMap and a Secret, turned into environment variables that backend/config.py reads.
UVICORN_WORKERS=1: in Kubernetes you scale by adding pods, not workers.
RUN_MIGRATIONS=false: stops each pod from migrating on startup.
REDIS_HOST=redis: this is the Redis Service name.
The database URL is in the Secret, which is where a real Postgres password would go.
- 03-redis.yaml: Redis as a single-pod StatefulSet with a 1 GiB volume, so data survives restarts, plus a Service named redis.
- 04-sqlite-storage.yaml: one volume holding sql_app.db, shared by the migration Job and all 3 backend pods.
This works only because a local cluster has one node: "ReadWriteOnce" means one node, not one pod.
On a multi-node cluster you'd need Postgres instead.
- 05-migrate-job.yaml: a one-off Job that runs alembic upgrade head once before the API starts serving, so 3 pods don't race to create tables.
- 06-backend.yaml: the mystore-api Deployment with 3 replicas.
It passes in the pod name, namespace, IP and node name (the "Downward API"), which your /k8s/pod endpoint and the X-K8s-Pod-Name header read.
It points Kubernetes' health checks at your /k8s/probes/startupz, readyz and livez endpoints.
It waits 5 seconds before shutting a pod down, so traffic stops arriving first.
It mounts the SQLite volume and sets CPU and memory limits.
It also defines a Service on port 30800 and a PodDisruptionBudget that keeps at least 2 pods up during maintenance.
- 07-frontend.yaml: the mystore-frontend Deployment with 3 nginx replicas, health checks on /healthz, a Service on port 30080, and a PodDisruptionBudget.
- 08-network-policy.yaml: only backend pods may connect to Redis. Docker Desktop ignores this rule, but kind or minikube with Calico enforce it.
- deploy.ps1: builds mystore-api:local and mystore-frontend:local, then applies the manifests.

It waits for Redis, then for the migration, then for both Deployments.
It re-runs the migration Job on each deploy (a finished Job can't be updated) and restarts the pods so new images are used.
On kind or minikube it also copies the images into the cluster.

**Files in frontend/ (new)**
- Dockerfile: a two-stage build. Node 22 builds the React app with VITE_API_URL=/api, then a small nginx:1.27-alpine image serves it. The build overrides vite.config.ts's GitHub Pages path (/mystore_fastapi/) to serve from /, so the GitHub Pages deploy still works.
- nginx.conf: serves the app, adds a /healthz check, and forwards /api/* to http://mystore-api:8000/. Buffering is off so the live cart events (/card/events/live) stream properly.
- .dockerignore: keeps node_modules, dist and your notes out of the image.

***Changes to existing backend files***
backend/entrypoint.sh: migrations now run only when RUN_MIGRATIONS is true. It defaults to true, so Docker Compose behaves as before.
backend/.dockerignore: now excludes .myenv, dump.rdb and dump.json, which were being copied into the image.
backend/config.py and backend/k8s/k8s_adapters.py: Jobs created by POST /k8s/cluster/jobs/trigger used a hardcoded mystore-api:latest image. It's now a new K8S_JOB_IMAGE setting, defaulting to mystore-api:local.

The other Python files you mentioned (k8s_middleware.py, k8s_ports.py, k8s_router.py, k8s_schemas.py, k8s_service.py) already work in-cluster and didn't need changes.

**Things to know**
- Removed files: I replaced the five earlier k8s/*.yaml files. Your backend/k8s/plan.md still names them (for example 00-namespace-rbac.yaml), so those commands are out of date. I also dropped:
The autoscaler: it would override the fixed 3 replicas you asked for, and Docker Desktop lacks the metrics service it needs.
The CronJob: it only called a health endpoint.
- Redis is a dependency of every backend pod: if Redis is down, all 3 backend pods report "not ready" and the API stops taking traffic. Backend pods that start before Redis may restart a few times, which is normal; the script waits for Redis first to avoid this.
- Only one pod runs the purchase-stream consumer: the existing Redis leader lock makes sure of that.
- Docker Desktop's two cluster types: the default ("kubeadm") sees images you build locally. If you chose the "kind" type, images may not be visible and pods will fail to pull them; switch to kubeadm or load the images with kind load docker-image.