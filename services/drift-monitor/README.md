# drift-monitor

One-shot job (Kubernetes CronJob) that compares the last window of prediction logs with the
reference sample of the served model, saves an Evidently report and publishes `drift.detected`
(`libs/contracts/events/drift.detected.v1.json`) when a threshold is crossed.

## One run (`python -m monitor`)

1. Reads the partitions `predictions/dt=YYYY-MM-DD/hour=HH/` of the last `WINDOW_HOURS` hours
   (the current hour included). Below `MIN_WINDOW_ROWS` rows it stops without a report.
2. Reads `datasets/reference/reference.parquet`, the test block of the champion with its
   `fraud_score` and `label` (written by `pipelines`, replaced whenever `@champion` moves).
3. Runs Evidently `DataDriftPreset` on `v1`..`v28` and `amount` (current window sampled to
   `MAX_REPORT_ROWS`). A feature is drifted when its per-column drift test fails; Evidently picks
   the test from the sample size (K-S p-value up to 1000 rows, normed Wasserstein above).
4. Data incident signals: `missing_features` (column absent, more than half null, or stuck on
   a single value while the reference varies) and `out_of_range_share` (rows with a feature
   outside the reference range widened by `RANGE_MARGIN` of its span, or a negative amount).
   Missing features count as drifted in `drift_share`.
5. PR-AUC and recall at 90 % precision on the rows that carry a `label` (at least
   `MIN_LABELED_ROWS` rows and `MIN_LABELED_FRAUDS` frauds), and the same PR-AUC on the reference.
6. Writes `drift-reports/YYYY/MM/DD/HH/<report_id>.html` (Evidently) and `.json` (our summary
   plus the Evidently snapshot).
7. Publishes `drift.detected`, keyed by `report_id`, when drift share > `DRIFT_SHARE_THRESHOLD`,
   or PR-AUC is more than `PR_AUC_DROP_THRESHOLD` below the reference, or a feature is missing,
   or the out-of-range share exceeds `OUT_OF_RANGE_THRESHOLD`.

Evidently is pinned to `0.7.23` (new `Report` / `Dataset` / `DataDefinition` API, results read
from the snapshot tests). It does not import with pandas 3, hence `pandas<3`.

## Configuration

| Variable | Default |
|---|---|
| `KAFKA_BOOTSTRAP_SERVERS` | `localhost:9092` |
| `S3_ENDPOINT_URL` | unset (`http://minio:9000` in compose), with the AWS credential variables |
| `REFERENCE_URI` | `s3://datasets/reference/reference.parquet` |
| `PREDICTIONS_URI` | `s3://predictions` |
| `REPORTS_URI` | `s3://drift-reports` |
| `WINDOW_HOURS` / `MIN_WINDOW_ROWS` / `MAX_REPORT_ROWS` | `1` / `200` / `50000` |
| `DRIFT_SHARE_THRESHOLD` | `0.3` |
| `PR_AUC_DROP_THRESHOLD` | `0.05` |
| `OUT_OF_RANGE_THRESHOLD` / `RANGE_MARGIN` | `0.05` / `0.1` |
| `MIN_LABELED_ROWS` / `MIN_LABELED_FRAUDS` | `200` / `5` |

Any URI may be a local path instead of `s3://`, which is how the tests run.

## Run and test

```bash
uv sync
S3_ENDPOINT_URL=http://localhost:9000 AWS_ACCESS_KEY_ID=minio AWS_SECRET_ACCESS_KEY=minio12345 \
  uv run python -m monitor
uv run ruff check . && uv run ruff format --check .
uv run pytest -q
```
