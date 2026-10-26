import argparse
import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import mlflow
import mlflow.xgboost
import pandas as pd
import yaml
from mlflow import MlflowClient
from mlflow.models import infer_signature
from xgboost import XGBClassifier

from data.ingest import DEFAULT_SOURCE, load_source, prepare
from data.schema import FEATURES, TARGET, TIME
from data.storage import write_parquet
from data.validate import validate
from registry import reference
from registry.promote import (
    CHALLENGER,
    CHAMPION,
    alias_version,
    bootstrap_champion,
    default_model_name,
)
from training.evaluate import GateResult, Metrics, compare, evaluate
from training.features import Split, select_window, time_stratified_split, xy

log = logging.getLogger(__name__)

DEFAULT_CONFIG = Path(__file__).resolve().parents[1] / "configs" / "xgb_baseline.yaml"
CHAMPION_METRICS = ("pr_auc", "recall_at_p90", "p95_latency_ms")


@dataclass(frozen=True)
class TrainConfig:
    params: dict[str, Any]
    experiment: str = "fraud-xgb"
    model_name: str = field(default_factory=default_model_name)
    fractions: tuple[float, float, float] = (0.7, 0.15, 0.15)
    early_stopping_rounds: int = 40
    latency_samples: int = 200
    max_p95_ms: float = 50.0
    synthetic_rows: int = 284_807
    synthetic_fraud_rate: float = 0.00172

    @classmethod
    def load(cls, path: str | Path) -> "TrainConfig":
        raw = yaml.safe_load(Path(path).read_text())
        synthetic = raw.pop("synthetic", {})
        split = raw.pop("split", {})
        return cls(
            **raw,
            fractions=tuple(split.get("fractions", cls.fractions)),
            synthetic_rows=synthetic.get("rows", cls.synthetic_rows),
            synthetic_fraud_rate=synthetic.get("fraud_rate", cls.synthetic_fraud_rate),
        )


@dataclass(frozen=True)
class TrainingResult:
    mlflow_run_id: str
    model_name: str
    version: str
    metrics: Metrics
    gate: GateResult
    champion_version: str | None
    reference_uri: str


def fit(split: Split, config: TrainConfig) -> XGBClassifier:
    x_train, y_train = xy(split.train)
    positives = int(y_train.sum())
    model = XGBClassifier(
        **config.params,
        scale_pos_weight=(len(y_train) - positives) / max(positives, 1),
        early_stopping_rounds=config.early_stopping_rounds,
    )
    model.fit(x_train, y_train, eval_set=[xy(split.valid)], verbose=False)
    return model


def score_champion(
    client: MlflowClient, config: TrainConfig, test: pd.DataFrame
) -> tuple[str | None, Metrics | None]:
    version = alias_version(client, config.model_name, CHAMPION)
    if version is None:
        return None, None
    champion = mlflow.xgboost.load_model(f"models:/{config.model_name}/{version}")
    return version, evaluate(champion, *xy(test), config.latency_samples)


def reference_sample(model: XGBClassifier, test: pd.DataFrame, version: str) -> pd.DataFrame:
    sample = test[FEATURES].reset_index(drop=True)
    sample["fraud_score"] = model.predict_proba(test[FEATURES])[:, 1]
    sample["label"] = test[TARGET].to_numpy()
    sample["model_version"] = version
    return sample


def describe_window(data: pd.DataFrame, window_days: float | None) -> str:
    days = "all" if window_days is None else f"{window_days:g}d"
    return f"time={data[TIME].min():.0f}..{data[TIME].max():.0f};days={days}"


def train(
    frame: pd.DataFrame,
    config: TrainConfig,
    *,
    window_days: float | None = None,
    agent_run_id: str | None = None,
    bootstrap: bool = False,
    reference_root: str | None = None,
) -> TrainingResult:
    validate(frame)
    data = select_window(prepare(frame), window_days)
    split = time_stratified_split(data, config.fractions)
    window = describe_window(data, window_days)
    client = MlflowClient()
    mlflow.set_experiment(config.experiment)

    run_tags = {"data_window": window} | ({"agent_run_id": agent_run_id} if agent_run_id else {})
    with mlflow.start_run(tags=run_tags) as run:
        model = fit(split, config)
        metrics = evaluate(model, *xy(split.test), config.latency_samples)
        champion_version, champion = score_champion(client, config, split.test)
        gate = compare(champion and champion.to_dict(), metrics.to_dict(), config.max_p95_ms)

        mlflow.log_params(
            config.params
            | {
                "scale_pos_weight": round(model.get_params()["scale_pos_weight"], 3),
                "best_iteration": model.best_iteration,
                "early_stopping_rounds": config.early_stopping_rounds,
                "window_days": window_days or "all",
                "rows": len(data),
            }
        )
        mlflow.log_metrics(metrics.to_dict())
        if champion:
            champion_values = champion.to_dict()
            mlflow.log_metrics({f"champion_{k}": champion_values[k] for k in CHAMPION_METRICS})
        mlflow.set_tag("gate_passed", str(gate.passed).lower())
        mlflow.log_dict({"split": split.summary(), "gate": asdict(gate)}, "evaluation.json")
        example = split.test[FEATURES].head(5)
        info = mlflow.xgboost.log_model(
            model,
            name="model",
            input_example=example,
            signature=infer_signature(example, model.predict_proba(example)),
            registered_model_name=config.model_name,
        )

    version = str(info.registered_model_version)
    reference_uri = write_parquet(
        reference_sample(model, split.test, version),
        reference.versioned_uri(version, reference_root),
    )
    version_tags = {"data_window": window, "reference_uri": reference_uri}
    for key, value in (version_tags | ({"run_id": agent_run_id} if agent_run_id else {})).items():
        client.set_model_version_tag(config.model_name, version, key, value)
    client.set_registered_model_alias(config.model_name, CHALLENGER, version)
    if bootstrap:
        bootstrap_champion(config.model_name, version, client, reference_root)

    return TrainingResult(
        run.info.run_id, config.model_name, version, metrics, gate, champion_version, reference_uri
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Train the XGBoost fraud model")
    parser.add_argument("--data", default=str(DEFAULT_SOURCE), help="csv/parquet, local or s3://")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--window-days", type=float, default=None)
    parser.add_argument("--run-id", default=None, help="agent run that requested this training")
    parser.add_argument("--bootstrap-champion", action="store_true")
    parser.add_argument("--reference-root", default=None)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")

    config = TrainConfig.load(args.config)
    frame, origin = load_source(
        args.data,
        synthetic_rows=config.synthetic_rows,
        fraud_rate=config.synthetic_fraud_rate,
    )
    log.info("training on %d rows from %s", len(frame), origin)
    result = train(
        frame,
        config,
        window_days=args.window_days,
        agent_run_id=args.run_id,
        bootstrap=args.bootstrap_champion,
        reference_root=args.reference_root,
    )
    print(json.dumps(asdict(result), indent=2))


if __name__ == "__main__":
    main()
