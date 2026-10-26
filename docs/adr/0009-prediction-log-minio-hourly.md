# 0009. Prediction log on MinIO, partitioned by scoring hour

Date: 2026-10-26. Status: accepted.

## Context

Drift detection needs the features and scores the model actually saw, by time window. Retraining needs the same rows once labels arrive. The backend database holds transactions for the dashboard, but scanning it from batch jobs would load the operational store, and the drift monitor and the retrain Job already read Parquet from MinIO.

## Decision

fastapi-ml buffers every scored row (`transaction_id`, `timestamp`, `v1`..`v28`, `amount`, `fraud_score`, `is_fraud`, `model_version`, `latency_ms`, nullable `label`) and writes Parquet files to `predictions/dt=YYYY-MM-DD/hour=HH/part-<uuid>.parquet`, partitioned by the scoring time, flushing at 1 000 rows or 60 s (`PREDICTION_LOG_MAX_ROWS`, `PREDICTION_LOG_MAX_SECONDS`). Every replica writes its own files; nothing is appended or rewritten. drift-monitor reads the partitions of the last `WINDOW_HOURS`; the retrain Job reads the last `WINDOW_DAYS` and keeps labeled rows, one per `transaction_id`.

## Consequences

- A drift window is a list of prefixes, no scan of the whole log and no query engine.
- Writers never coordinate: a uuid per file, so replicas and restarts cannot overwrite each other.
- The window is the scoring hour, not the transaction timestamp; a replayed backlog lands in the hour it was scored, which is what the served model saw.
- Up to 60 s of rows can be lost if a replica is killed without a graceful shutdown; the lifespan flushes on a normal stop.
- Many small files per hour under heavy load; acceptable at the project's volumes, compaction would be the next step.
- Labels arriving later are in the log only when they come with the transaction (simulator, demo); a label feedback path would write to the same layout.
