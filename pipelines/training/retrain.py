"""Entry point of the retrain Job, see docs/architecture/retrain-contract.md."""

import json
import logging
import os
import sys
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from data.ingest import load_source, prepare
from data.schema import FEATURES, RAW_COLUMNS, TARGET, TIME
from data.storage import list_files, read_table
from data.validate import validate
from training.features import Split, split_newest, time_stratified_split
from training.train import TrainConfig, TrainingResult, train_on_split

log = logging.getLogger(__name__)

PIPELINES_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EVAL_SHARE = 0.3
DEFAULT_MIN_EVAL_FRAUDS = 20


@dataclass(frozen=True)
class RetrainSettings:
    run_id: str
    window_days: float = 7.0
    train_config: str = "configs/xgb_baseline.yaml"
    data_uri: str = "s3://datasets/raw/creditcard.parquet"
    predictions_uri: str = "s3://predictions/"

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "RetrainSettings":
        run_id = env.get("RUN_ID", "").strip()
        if not run_id:
            raise ValueError("RUN_ID is required")
        window_days = float(env.get("WINDOW_DAYS") or cls.window_days)
        if window_days <= 0:
            raise ValueError("WINDOW_DAYS must be positive")
        return cls(
            run_id=run_id,
            window_days=window_days,
            train_config=env.get("TRAIN_CONFIG") or cls.train_config,
            data_uri=env.get("DATA_URI") or cls.data_uri,
            predictions_uri=env.get("PREDICTIONS_URI") or cls.predictions_uri,
        )

    def config_path(self) -> Path:
        path = Path(self.train_config)
        return path if path.is_absolute() or path.exists() else PIPELINES_ROOT / path


@dataclass(frozen=True)
class RetrainResult:
    training: TrainingResult
    eval_slice: str
    labeled_rows: int


def partition_prefixes(uri: str, since: datetime, until: datetime) -> list[str]:
    root = uri.removeprefix("file://").rstrip("/")
    days = (until.date() - since.date()).days
    return [f"{root}/dt={since.date() + timedelta(days=d):%Y-%m-%d}/" for d in range(days + 1)]


def load_labeled_predictions(
    uri: str, since: datetime, until: datetime, client: Any = None
) -> pd.DataFrame:
    """Labeled rows of the prediction log scored in [since, until], one per transaction."""
    files = [
        file
        for prefix in partition_prefixes(uri, since, until)
        for file in list_files(prefix, client=client)
    ]
    columns = ["transaction_id", "timestamp", *FEATURES, "label"]
    if not files:
        return pd.DataFrame(columns=columns)
    frame = pd.concat([read_table(file, client)[columns] for file in files], ignore_index=True)
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    features = frame[FEATURES].astype("float64")
    usable = (
        frame["timestamp"].between(since, until)
        & frame["label"].isin([0, 1])
        & np.isfinite(features).all(axis=1)
        & (features["amount"] >= 0)
    )
    labeled = frame[usable].sort_values("timestamp", kind="stable")
    return labeled.drop_duplicates("transaction_id", keep="last").reset_index(drop=True)


def to_training_rows(predictions: pd.DataFrame, time_origin: float) -> pd.DataFrame:
    """Prediction log rows in the dataset schema, placed on the time axis after the base data."""
    if predictions.empty:
        return pd.DataFrame(columns=RAW_COLUMNS).astype({c: "float64" for c in RAW_COLUMNS})
    timestamps = pd.to_datetime(predictions["timestamp"], utc=True)
    rows = predictions[FEATURES].astype("float64").reset_index(drop=True)
    seconds = (timestamps - timestamps.min()).dt.total_seconds().to_numpy()
    rows.insert(0, TIME, time_origin + 1.0 + seconds)
    rows[TARGET] = predictions["label"].astype("int64").to_numpy()
    return rows[RAW_COLUMNS]


def build_split(base: pd.DataFrame, recent: pd.DataFrame, config: TrainConfig) -> tuple[Split, str]:
    """Test on the newest labeled predictions, cut by time so the slice is strictly later than
    every training row. Without enough labeled frauds there, fall back to the usual
    time-ordered split of base and recent rows together."""
    eval_share = config.retrain.get("eval_share", DEFAULT_EVAL_SHARE)
    min_frauds = int(config.retrain.get("min_eval_frauds", DEFAULT_MIN_EVAL_FRAUDS))
    if len(recent):
        cut = recent[TIME].quantile(1 - eval_share)
        newest = recent[recent[TIME] >= cut].reset_index(drop=True)
        frauds = int(newest[TARGET].sum())
        if min_frauds <= frauds < len(newest):
            pool = pd.concat([base, recent[recent[TIME] < cut]], ignore_index=True)
            valid_share = config.fractions[1] / (config.fractions[0] + config.fractions[1])
            train, valid = split_newest(pool, valid_share)
            return Split(train, valid, newest), "recent"
        log.warning(
            "newest labeled slice has %d frauds out of %d rows, need %d: using the holdout split",
            frauds,
            len(newest),
            min_frauds,
        )
    combined = pd.concat([base, recent], ignore_index=True)
    return time_stratified_split(combined, config.fractions), "holdout"


def retrain(
    settings: RetrainSettings,
    config: TrainConfig,
    *,
    now: datetime | None = None,
    client: Any = None,
    reference_root: str | None = None,
) -> RetrainResult:
    frame, origin = load_source(
        settings.data_uri,
        synthetic_rows=config.synthetic_rows,
        fraud_rate=config.synthetic_fraud_rate,
        client=client,
    )
    validate(frame)
    base = prepare(frame)
    until = now or datetime.now(UTC)
    since = until - timedelta(days=settings.window_days)
    predictions = load_labeled_predictions(settings.predictions_uri, since, until, client)
    recent = to_training_rows(predictions, float(base[TIME].max()))
    log.info("base %d rows from %s, %d labeled predictions", len(base), origin, len(recent))

    split, eval_slice = build_split(base, recent, config)
    window = (
        f"days={settings.window_days:g};from={since:%Y-%m-%dT%H:%M}Z;to={until:%Y-%m-%dT%H:%M}Z"
        f";labeled={len(recent)}"
    )
    result = train_on_split(
        split,
        config,
        data_window=window,
        params={"window_days": settings.window_days, "rows": len(base) + len(recent)}
        | {"base_rows": len(base), "labeled_rows": len(recent)},
        run_tags={"eval_slice": eval_slice, "data_uri": settings.data_uri},
        agent_run_id=settings.run_id,
        reference_root=reference_root,
    )
    return RetrainResult(result, eval_slice, len(recent))


def main(env: Mapping[str, str] | None = None) -> int:
    """Exit 0 whether or not the gate passed; non-zero only when the retrain itself failed."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    try:
        settings = RetrainSettings.from_env(os.environ if env is None else env)
        config = TrainConfig.load(settings.config_path())
        result = retrain(settings, config)
    except Exception:
        log.exception("retrain failed")
        return 1
    training = result.training
    summary = {
        "run_id": settings.run_id,
        "model_name": training.model_name,
        "version": training.version,
        "champion_version": training.champion_version,
        "gate_passed": training.gate.passed,
        "gate_reasons": training.gate.reasons,
        "eval_slice": result.eval_slice,
        "labeled_rows": result.labeled_rows,
        "metrics": asdict(training.metrics),
        "reference_uri": training.reference_uri,
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
