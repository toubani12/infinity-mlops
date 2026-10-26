# Observability

Prometheus scrapes the services every 10 s and Grafana shows the **Infinity MLOps** dashboard (home page, anonymous read-only access, admin login `admin` / `GRAFANA_ADMIN_PASSWORD`).

| | Compose (`make up-apps`) | Kubernetes |
|---|---|---|
| Prometheus | http://localhost:9090 (`PROMETHEUS_HOST_PORT`) | `kubectl -n infinity port-forward svc/prometheus 9090:9090` |
| Grafana | http://localhost:3001 (`GRAFANA_HOST_PORT`) | `kubectl -n infinity port-forward svc/grafana 3001:3000`, or NodePort 30301 on minikube |
| Scrape config | `infra/observability/prometheus.yml`, static targets | `k8s/base/observability/prometheus/prometheus.yml`, one target per pod from the EndpointSlices of each Service |
| Grafana provisioning and dashboard | mounted from `k8s/base/observability/grafana/` | ConfigMaps generated from the same files |

Edit the dashboard in `k8s/base/observability/grafana/dashboards/infinity-mlops.json`; Grafana does not save UI changes to provisioned dashboards. Prometheus keeps two days of data, on a volume under Compose and in an `emptyDir` on Kubernetes (lost when the pod restarts).

## Targets and metrics

| Job | Endpoint | Metrics used by the dashboard |
|---|---|---|
| `fastapi-ml` | `:8000/metrics` | `http_request_duration_seconds` (labels `path`, `status`), `predictions_total{outcome, model_version, source}`, `fraud_score`, `kafka_messages_total{result}`, `kafka_batch_size`, `served_model_info{version}`, `model_reloads_total{result}` |
| `agents-langgraph` | `:8100/metrics` | `agent_drift_share`, `agent_drift_alert_timestamp_seconds`, `agent_runs_finished_total{outcome}`, `agent_active_run` |
| `backend-spring` | `:8080/actuator/prometheus` | `infinity_outbox_published_total`, `infinity_outbox_failed_total`, `infinity_alerts_created_total`, plus the Spring Boot defaults (`http_server_requests_seconds`, JVM, HikariCP) |

## Why drift_share comes from the agent

drift-monitor is a one-shot CronJob: it runs for a few seconds and exits, so there is nothing to scrape. The two honest options were a Pushgateway that each run pushes to, or reading the value where it already arrives. We took the second: the agent consumes every `drift.detected`, so it exposes `agent_drift_share` and `agent_drift_alert_timestamp_seconds` from the message. No extra component, no change to drift-monitor.

The limit: drift-monitor publishes only when a threshold is crossed, so the panel shows the drift share of the last alert, not of every monitored window, and the gauges read 0 after an agent restart. The **Last drift alert** panel says how old that value is. Every report, below threshold or not, is in MinIO under `drift-reports/` and on the dashboard's Drift page through the backend. If the team later needs a time series of every window, add a Pushgateway and push `drift_share` at the end of `monitor.__main__.run`.

## Checks

```bash
curl -s localhost:9090/api/v1/targets | jq '.data.activeTargets[] | {job: .labels.job, health}'
curl -s localhost:8000/metrics | grep predictions_total
```

A target `down` in Compose usually means its container is not running (`make ps`). On Kubernetes, check that the Service still has a port named `http`: the scrape config keeps only that port.
