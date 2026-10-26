# pipelines

Batch code for the fraud model: ingestion, validation, feature split, training and registry
operations. It runs locally and inside the retrain Kubernetes Job.

## Data

The real dataset is the ULB credit card CSV at `data/creditcard.csv` (repo root, git-ignored).
When it is absent, every entry point falls back to `data/synthetic.py`, which produces a frame
with the same columns and casing: `Time` in seconds over two days with a night trough, `V1`..`V28`
with decreasing variance, a log-normal `Amount`, and frauds shifted on the components that
separate them in the real data (`V14`, `V12`, `V10`, `V17`, `V4`, ...). About a fifth of the
frauds are close to legitimate traffic, which keeps the baseline PR-AUC in the 0.8 range.

```bash
uv run python -m data.synthetic --rows 284807 --fraud-rate 0.00172 --out ../data/synthetic.csv
```

## Ingestion and validation

```bash
uv run python -m data.ingest --src ../data/creditcard.csv --dest s3://datasets/raw/creditcard.parquet
```

Column names are normalized to lowercase (`time`, `v1`..`v28`, `amount`, `class`), the frame is
validated, sorted by time and written as parquet to a local path or to MinIO
(`S3_ENDPOINT_URL`, falling back to `MLFLOW_S3_ENDPOINT_URL`, credentials from
`AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`). Without `--dest`, the destination is the S3 URI
when an endpoint is configured and `data/raw/creditcard.parquet` otherwise.

`data.validate.validate` returns a `ValidationReport` (rows, frauds, errors, warnings) and raises
`DataValidationError` on errors: missing expected column (31 expected), non-numeric dtype, missing
or infinite value, negative amount, class outside `{0, 1}`, empty frame. Extra columns, duplicated
rows and the absence of frauds are warnings only (the real file has about 1 000 duplicates).

## Time-ordered stratified split

`training.features.time_stratified_split` returns train / valid / test blocks (70 / 15 / 15 by
default). Rows are sorted by `time`, then each class is cut at its own time quantiles: the first
70 % of legitimate rows and the first 70 % of frauds go to train, and so on. Every block keeps
the global fraud rate, and within a class nothing from the future reaches an earlier block.

A single cut time per boundary cannot keep the ratio, because fraud intensity follows its own
day/night cycle: on the synthetic two-day data a plain time cut gives train a fraud rate about 50 % higher
than test. The price of per-class cuts is a short overlap between neighbouring blocks (about
three hours between train and valid on the full synthetic data). Valid only drives early
stopping; the split raises `ValueError` if any training row reaches into the test period, so
test metrics are always measured on data strictly later than everything the model learned from.
`Split.summary()` reports rows, frauds, fraud rate and time range per block.

## Training

```bash
MLFLOW_TRACKING_URI=http://localhost:5000 uv run python -m training.train \
  --data ../data/creditcard.csv --config configs/xgb_baseline.yaml --bootstrap-champion
```

Options: `--window-days N` keeps the last N days of data, `--run-id` is the agent run that asked
for the training (stored as the `run_id` tag of the model version), `--reference-root` overrides
where reference samples go. `--data` accepts a local or `s3://` CSV or parquet; a missing local
file falls back to synthetic data.

One run:

1. validates the frame, applies the window and the time-ordered stratified split;
2. fits `XGBClassifier` with `scale_pos_weight = negatives / positives` of the train block and
   early stopping on the valid block (`configs/xgb_baseline.yaml`);
3. evaluates on the test block: `pr_auc`, `recall_at_p90`, `roc_auc`, `p95_latency_ms`
   (single-row `predict_proba` calls);
4. when a champion exists, evaluates it on the same test block, logs `champion_pr_auc`,
   `champion_recall_at_p90`, `champion_p95_latency_ms` and the `gate_passed` tag
   (`training.evaluate.compare`: PR-AUC and recall at 90 % precision both at least the champion's,
   p95 under 50 ms);
5. logs params, metrics, `evaluation.json` (split summary, gate reasons) and the model
   (`mlflow.xgboost`), registers it as `fraud-xgb` (`MODEL_NAME`) and sets `@challenger`;
6. writes the reference sample (test block with `fraud_score`, `label`, `model_version`) to
   `<root>/v<version>/reference.parquet`, root being `s3://datasets/reference` when
   `S3_ENDPOINT_URL` or `MLFLOW_S3_ENDPOINT_URL` is set and `data/reference` otherwise.

`--bootstrap-champion` sets `@champion` on the new version when no champion exists yet, for the
very first model. Consumers load the model with
`mlflow.xgboost.load_model("models:/fraud-xgb@champion")` and call `predict_proba`.

## Registry

```bash
uv run python -m registry.promote                  # @champion -> version behind @challenger
uv run python -m registry.promote --version 3      # explicit version, also used for rollback
```

The command prints `{"model_name", "version", "alias", "previous_version"}`, the fields of
`model.promoted`. Whenever `@champion` moves, the version's reference sample is copied to
`<root>/reference.parquet`, the file drift-monitor reads, so drift is always measured against the
data of the model being served.

## Tests

```bash
uv sync
uv run ruff check . && uv run ruff format --check .
uv run pytest -q
```
