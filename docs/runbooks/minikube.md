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

Overrides: `MINIKUBE_CNI` (see [Network policies](#network-policies)), `MINIKUBE_PROFILE`, `MINIKUBE_MEMORY`, `MINIKUBE_CPUS`, `MINIKUBE_DISK`, `NEXT_PUBLIC_API_BASE_URL` (baked into the dashboard image, default `http://localhost:8080`), `SKIP_BUILD=1` to redeploy without rebuilding, `ROLLOUT_TIMEOUT`.

## Access

```bash
kubectl -n infinity port-forward svc/backend-spring 8080:8080
kubectl -n infinity port-forward svc/frontend-next 3000:3000
kubectl -n infinity port-forward svc/mlflow 5000:5000
kubectl -n infinity port-forward svc/minio 9001:9001
kubectl -n infinity port-forward svc/grafana 3001:3000        # dashboards, see observability.md
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
| backend, dashboard and Grafana Services | ClusterIP | NodePort (30080, 30300, 30301) |
| Prometheus and Grafana requests and limits | 100m / 256-512 Mi | 25-50m / 320-384 Mi limit |

## Network policies

`k8s/base/network-policies` denies all ingress in namespace `infinity`, then allows only the flows the platform uses (egress is not restricted, so DNS, the Kubernetes API and image pulls need no rule):

| Destination | Port | Allowed sources |
|---|---|---|
| kafka | 9092 | backend-spring, fastapi-ml, agents-langgraph, drift-monitor, kafka-topics Job, kafka itself, pods labelled `app.kubernetes.io/name: pipelines` |
| postgres | 5432 | backend-spring, mlflow, agents-langgraph |
| minio | 9000 | mlflow, fastapi-ml, drift-monitor, agents-langgraph, minio-buckets Job, retrain and bootstrap Jobs |
| mlflow | 5000 | fastapi-ml, agents-langgraph, drift-monitor, retrain and bootstrap Jobs |
| backend-spring, frontend-next, grafana | 8080, 3000, 3000 | any (browsers, NodePorts) |
| prometheus | 9090 | grafana |
| fastapi-ml, agents-langgraph | 8000, 8100 | prometheus |

Retrain Jobs are matched by `app.kubernetes.io/component: retrain` (set in `k8s/jobs/retrain-job.yaml`), the e2e bootstrap Job by `component: bootstrap`. A new workload that talks to one of these services needs its label added to the matching policy, and a one-off Job running the pipelines image (drift simulator) needs `app.kubernetes.io/name: pipelines` to reach Kafka. Kubelet probes and `kubectl port-forward` are not affected.

minikube's default CNI ignores NetworkPolicy objects, so the policies are applied but not enforced. To enforce them, create the profile with Calico:

```bash
minikube -p infinity delete            # the CNI is fixed when the profile is created
MINIKUBE_CNI=calico make minikube
```

kind's default CNI (kindnet, kind 0.24 and later) enforces them, so `e2e-kind.yml` runs the demo with the policies active.

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
