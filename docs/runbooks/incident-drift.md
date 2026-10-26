# Incident: drift.detected fired

drift-monitor (CronJob, hourly; every 5 minutes on minikube) compares the last hour of the prediction log with the reference sample of the served champion and publishes `drift.detected` when one threshold is crossed. The agent reacts on its own; this page is for the human who looks at the alert or has to approve what follows.

## 1. Find the alert

| Where | What |
|---|---|
| Dashboard, **Drift** page | every report the backend received, with drift share, drifted and missing features, PR-AUC against the reference |
| Dashboard, **Agent** page | the run started for the alert (`run_id` derives from `report_id`), its steps and decision |
| Grafana, **drift_share** and **Last drift alert** | drift share of the last alert and its age ([observability](observability.md)) |
| MinIO `drift-reports/YYYY/MM/DD/HH/<report_id>.html` and `.json` | the Evidently report and our summary |
| Kafka | `kafka-console-consumer.sh --topic drift.detected --from-beginning` |

## 2. Read the report

| Field | Meaning | Threshold (env of drift-monitor and agent) |
|---|---|---|
| `drift_share` | share of `v1`..`v28`, `amount` whose per-column drift test failed; missing features count as drifted | `DRIFT_SHARE_THRESHOLD` 0.3 |
| `drifted_features` | the columns behind the share; amount and `v14`, `v12`, `v10`, `v17` matter most for fraud | |
| `missing_features` | column absent, mostly null, or filled with one value that is rare in the reference (a default `0.0`) | `MISSING_SHARE_THRESHOLD` 0.1 |
| `out_of_range_share` | rows with a feature outside the reference range widened by 10 %, or a negative amount | `OUT_OF_RANGE_THRESHOLD` 0.05 |
| `metrics.pr_auc` vs `metrics.reference_pr_auc` | PR-AUC on the labeled rows of the window against the reference; `labeled_rows` says how many | drop > `PR_AUC_DROP_THRESHOLD` 0.05 |
| `window` | start, end and row count of the analysed window | `MIN_WINDOW_ROWS` 200 |

The HTML report shows each column's distribution against the reference and the test used (K-S up to 1 000 rows, normed Wasserstein above).

## 3. What the agent decided

| Qualification | Rule | What happens | What you do |
|---|---|---|---|
| `data_incident` | a missing feature, or out-of-range share above threshold | run `ESCALATED`, no retrain: retraining on broken data would teach the model the outage | fix the upstream feed (which columns, since when: `window`); the champion keeps serving |
| `noise` | drift share and PR-AUC drop both under threshold | run `NOISE`, nothing else | nothing, unless the same features drift window after window |
| `real_drift` | otherwise | retrain Job `retrain-<run_id[:8]>`, gate, then approval request or `KEPT_CHAMPION` | review and decide (below) |

An alert that arrives while a run is open is attached to that run (`received` with `attached: true`), not retrained again.

## 4. Approve or reject

On the run page the comparison shows challenger and champion PR-AUC, recall at 90 % precision and p95 latency, measured on the same newest slice. The agent only asks when the challenger passed the gate (strictly better PR-AUC, recall not worse, p95 < 50 ms). Reject when:

- the window is too short or too few labels back the PR-AUC (`labeled_rows`, `eval_slice=holdout` tag on the MLflow run means no recent labeled slice was big enough);
- the drift has a known business cause that will revert (a campaign, a holiday);
- the challenger wins on PR-AUC but its latency is close to the limit.

Approve and reject need the `admin` role (`POST /api/agent/runs/{runId}/approve`, `/reject` with a reason). A rejection keeps the champion and the reason is stored on the run. Promotion moves `@champion`, publishes `model.promoted`, every fastapi-ml replica reloads and the reference sample used by drift-monitor follows.

## 5. If it goes wrong

- Promoted model misbehaves: [model rollback](model-rollback.md).
- Run stuck in `RUNNING` or `AWAITING_APPROVAL`, retrain Job failed: [agent stuck run](agent-stuck-run.md).
