# Minikube

Deploys the whole platform to a local minikube cluster with the `k8s/overlays/minikube` overlay. Needs minikube, kubectl and Docker, and 8 GB of memory free for the cluster (default on a 16 GB laptop).

## Bootstrap

```bash
make minikube
```

`scripts/bootstrap-minikube.sh`:

1. Starts the minikube profile `infinity` (8 GB, 4 CPUs, 30 GB disk) if it is not running, enables `metrics-server` and switches kubectl to that context.
2. Creates `k8s/overlays/minikube/secrets.env` from `secrets.env.example` if it is missing. The file is git-ignored; `secretGenerator` turns it into the `platform-secrets` Secret.
3. Builds every image that has a Dockerfile inside minikube (`minikube image build`), tagged `ghcr.io/toubani12/infinity-mlops/<service>:latest`. The overlay sets `imagePullPolicy: IfNotPresent`, so nothing is pulled from GHCR.
4. Deletes finished init Jobs, runs `kubectl apply -k k8s/overlays/minikube` and waits for Kafka, PostgreSQL, MinIO, the topic and bucket Jobs, then every Deployment whose image was built.

Overrides: `MINIKUBE_PROFILE`, `MINIKUBE_MEMORY`, `MINIKUBE_CPUS`, `MINIKUBE_DISK`, `NEXT_PUBLIC_API_BASE_URL` (baked into the dashboard image, default `http://localhost:8080`), `SKIP_BUILD=1` to redeploy without rebuilding, `ROLLOUT_TIMEOUT`.

## Access

```bash
kubectl -n infinity port-forward svc/backend-spring 8080:8080
kubectl -n infinity port-forward svc/frontend-next 3000:3000
kubectl -n infinity port-forward svc/mlflow 5000:5000
kubectl -n infinity port-forward svc/minio 9001:9001
```

Port-forwarding works with every minikube driver and matches the default `NEXT_PUBLIC_API_BASE_URL`. The backend and dashboard are also NodePorts 30080 and 30300; with the Docker driver on macOS, reach them through `minikube -p infinity service -n infinity frontend-next --url`.

## What the overlay changes

| Setting | Base | Minikube |
|---|---|---|
| Replicas of backend, inference, dashboard | 2 | 1 |
| Requests and limits | production-like | about half, sum of limits about 5 GB |
| Images | `:latest`, pulled | `:latest`, built in minikube, `IfNotPresent` |
| `drift-monitor` CronJob | hourly | every 5 minutes |
| backend Spring profile | default | `local` (enables `/api/auth/dev-token`) |
| backend and dashboard Services | ClusterIP | NodePort |

## Operate

```bash
kubectl -n infinity get pods
kubectl top pods -n infinity
kubectl -n infinity logs deploy/mlflow
kubectl -n infinity create job drift-now --from=cronjob/drift-monitor   # run a drift check immediately
make k8s-validate                                                       # render base and overlays without a cluster
```

## Reset

```bash
kubectl delete namespace infinity     # removes workloads and the PersistentVolumeClaims
minikube -p infinity delete           # removes the whole cluster
```

## Troubleshooting

- `ImagePullBackOff` on a service: its folder has no Dockerfile yet, or the build failed. Rerun `make minikube` once it exists.
- `kafka-topics` or `minio-buckets` Job retrying: the broker or MinIO is not ready yet; the Jobs retry up to 20 times.
- Pods `Pending` with insufficient memory: raise `MINIKUBE_MEMORY` and recreate the cluster (`minikube -p infinity delete`), memory cannot change on a running profile.
