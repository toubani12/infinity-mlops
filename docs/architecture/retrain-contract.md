# Retrain Job contract (agent ↔ pipelines)

Agreed between Badr (agents-langgraph) and Agrigah (pipelines, `k8s/jobs`). A change to this contract needs both owners to review it.

## Manifest

`k8s/jobs/retrain-job.yaml` (owned by Agrigah) is a plain `batch/v1` Job template, not part of any kustomization, that the agent loads, patches and creates in namespace `infinity`:

- `metadata.name`: placeholder `retrain-template`; the agent sets `retrain-<first 8 chars of run_id>`.
- `metadata.labels`: `app.kubernetes.io/part-of: infinity-mlops`, `app.kubernetes.io/component: retrain`; the agent adds `infinity.io/run-id: <run_id>`.
- `spec.backoffLimit: 0`, `spec.ttlSecondsAfterFinished: 3600`, `spec.activeDeadlineSeconds: 1800`.
- One container named `trainer`, image `ghcr.io/toubani12/infinity-mlops/pipelines:latest`, `envFrom` ConfigMap `platform-config` and Secret `platform-secrets`.
- Env vars the agent overrides on container `trainer`: `RUN_ID`, `WINDOW_DAYS` (default `7`), `TRAIN_CONFIG` (default `configs/xgb_baseline.yaml`), `DATA_URI` (default `s3://datasets/raw/creditcard.parquet`), `PREDICTIONS_URI` (default `s3://predictions/`).
- Container command: `python -m training.retrain` (Agrigah provides it): trains on the reference data plus labeled recent predictions within the window, evaluates champion and challenger on the most recent labeled slice, registers the new version, sets alias `challenger`, and exits 0 whether or not the gate passed (exit ≠ 0 only on technical failure).

## What the agent reads after the Job succeeds

- Model version of `fraud-xgb` carrying tag `run_id=<run_id>` (search with `MlflowClient.search_model_versions("name='fraud-xgb' and tag.run_id='<run_id>'")`); it also has alias `challenger`.
- On that version's training run: metrics `pr_auc`, `recall_at_p90`, `p95_latency_ms`, `champion_pr_auc`, `champion_recall_at_p90`, `champion_p95_latency_ms`; tag `gate_passed` = `true` | `false` and tag `gate_reasons` (short text).
- The champion version number from alias `champion`.

## Promotion

The agent, after human approval, calls `set_registered_model_alias("fraud-xgb", "champion", <challenger version>)` and publishes `model.promoted` (v1) with `previous_version`. fastapi-ml listens to `model.promoted` and reloads; if the reload fails it keeps the previous model and reports it in `/model` and its logs. Rollback (`reason: rollback`) is the same alias move back to `previous_version`.
