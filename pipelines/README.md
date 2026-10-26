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

## Tests

```bash
uv sync
uv run ruff check . && uv run ruff format --check .
uv run pytest -q
```
