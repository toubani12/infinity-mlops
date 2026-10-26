"""Replays transactions with gradual drift, sudden drift or a data incident, as a parquet file
or straight to the transaction.raw topic."""

import argparse
import asyncio
import json
import logging
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from data.ingest import DEFAULT_SOURCE, load_source, prepare
from data.schema import FEATURES, TARGET, TIME, V_FEATURES

log = logging.getLogger(__name__)

SCENARIOS = ("gradual", "sudden", "data-incident")
INCIDENTS = ("missing", "out-of-domain")
SHIFTED = ["v1", "v2", "v3", "v4", "v7", "v10", "v11", "v12", "v14", "v17", "amount"]
DISCRIMINANT = ["v3", "v4", "v10", "v11", "v12", "v14", "v16", "v17"]
MISSING = ["v4", "v10", "v12", "v14"]


def base_sample(
    data: pd.DataFrame, rows: int, fraud_rate: float | None, rng: np.random.Generator
) -> pd.DataFrame:
    """Recent rows (last 30 % of the timeline), frauds oversampled when `fraud_rate` is set."""
    recent = data[data[TIME] >= data[TIME].quantile(0.7)]
    frauds, legit = recent[recent[TARGET] == 1], recent[recent[TARGET] == 0]
    rate = recent[TARGET].mean() if fraud_rate is None else fraud_rate
    n_frauds = min(int(round(rows * rate)), rows)
    picked = pd.concat(
        [
            frauds.sample(
                n_frauds, replace=len(frauds) < n_frauds, random_state=rng.integers(2**31)
            ),
            legit.sample(
                rows - n_frauds,
                replace=len(legit) < rows - n_frauds,
                random_state=rng.integers(2**31),
            ),
        ]
    )
    return picked.sample(frac=1, random_state=rng.integers(2**31)).reset_index(drop=True)


def drift_weights(rows: int, scenario: str, change_at: float) -> np.ndarray:
    if scenario == "gradual":
        return np.linspace(0.0, 1.0, rows)
    return (np.arange(rows) >= int(rows * change_at)).astype(float)


def apply_drift(
    frame: pd.DataFrame,
    weights: np.ndarray,
    magnitude: float,
    concept: float,
    rng: np.random.Generator,
) -> pd.DataFrame:
    """Covariate shift on SHIFTED, plus concept drift: frauds borrow legitimate values on the
    discriminant components, which is what makes the served model lose PR-AUC."""
    out = frame.copy()
    legit = frame[frame[TARGET] == 0]
    frauds = np.flatnonzero(frame[TARGET].to_numpy() == 1)
    camouflaged = frauds[rng.random(frauds.size) < concept * weights[frauds]]
    if camouflaged.size and len(legit):
        donors = legit.sample(camouflaged.size, replace=True, random_state=rng.integers(2**31))
        out.loc[camouflaged, DISCRIMINANT] = donors[DISCRIMINANT].to_numpy()
    for feature in SHIFTED:
        if feature == "amount":
            out[feature] = out[feature] * (1 + magnitude * weights)
        else:
            out[feature] = out[feature] + magnitude * weights * frame[feature].std()
    return out


def apply_incident(
    frame: pd.DataFrame, incident: str, share: float, rng: np.random.Generator
) -> pd.DataFrame:
    out = frame.copy()
    hit = rng.random(len(out)) < share
    if incident == "missing":
        out.loc[hit, MISSING] = np.nan
    else:
        out.loc[hit, "amount"] = out.loc[hit, "amount"] * 1_000 + 50_000
        out.loc[hit, ["v14", "v17"]] = rng.choice([-60.0, 60.0], size=(int(hit.sum()), 2))
    return out


def with_identity(
    frame: pd.DataFrame,
    start: datetime,
    rate: float,
    labels_delay: float | None,
) -> pd.DataFrame:
    """Adds ids and timestamps; a label is kept only if it would have arrived by the end of the
    replay, i.e. when the row is at least `labels_delay` seconds older than the last one."""
    step = 1.0 / rate if rate > 0 else 0.001
    offsets = np.arange(len(frame)) * step
    out = pd.DataFrame(
        {
            "transaction_id": [str(uuid.uuid4()) for _ in range(len(frame))],
            "timestamp": [start + timedelta(seconds=float(o)) for o in offsets],
        }
    )
    out[FEATURES] = frame[FEATURES].to_numpy()
    labels = frame[TARGET].astype("Int64").to_numpy()
    if labels_delay is None:
        out["label"] = pd.array([pd.NA] * len(frame), dtype="Int64")
    else:
        known = offsets <= offsets[-1] - labels_delay
        out["label"] = pd.array(np.where(known, labels, pd.NA), dtype="Int64")
    return out


def simulate(
    data: pd.DataFrame,
    scenario: str,
    *,
    rows: int = 5_000,
    magnitude: float = 1.0,
    concept: float = 0.6,
    change_at: float = 0.2,
    incident: str = "missing",
    incident_share: float = 0.3,
    fraud_rate: float | None = None,
    labels_delay: float | None = 0.0,
    rate: float = 200.0,
    start: datetime | None = None,
    seed: int = 7,
) -> pd.DataFrame:
    if scenario not in SCENARIOS:
        raise ValueError(f"scenario must be one of {SCENARIOS}")
    rng = np.random.default_rng(seed)
    sample = base_sample(prepare(data), rows, fraud_rate, rng)
    if scenario == "data-incident":
        if incident not in INCIDENTS:
            raise ValueError(f"incident must be one of {INCIDENTS}")
        drifted = apply_incident(sample, incident, incident_share, rng)
    else:
        weights = drift_weights(rows, scenario, change_at)
        drifted = apply_drift(sample, weights, magnitude, concept, rng)
    return with_identity(drifted, start or datetime.now(UTC), rate, labels_delay)


def to_event(row: dict) -> dict:
    """transaction.raw v1; a feature lost upstream is sent as 0.0, the usual default fill,
    because the contract has no nullable feature."""
    event = {
        "transaction_id": row["transaction_id"],
        "timestamp": row["timestamp"].isoformat().replace("+00:00", "Z"),
        "amount": 0.0 if pd.isna(row["amount"]) else float(row["amount"]),
    }
    event |= {f: 0.0 if pd.isna(row[f]) else float(row[f]) for f in V_FEATURES}
    if not pd.isna(row["label"]):
        event["label"] = int(row["label"])
    return event


async def publish(
    transactions: pd.DataFrame,
    bootstrap_servers: str,
    topic: str = "transaction.raw",
    rate: float = 200.0,
    producer=None,
) -> int:
    if producer is None:
        from aiokafka import AIOKafkaProducer

        producer = AIOKafkaProducer(bootstrap_servers=bootstrap_servers, linger_ms=10)
    await producer.start()
    loop = asyncio.get_running_loop()
    started = loop.time()
    try:
        for position, row in enumerate(transactions.to_dict("records")):
            event = to_event(row)
            await producer.send(
                topic, json.dumps(event).encode(), key=row["transaction_id"].encode()
            )
            if rate > 0:
                await asyncio.sleep(max(0.0, started + (position + 1) / rate - loop.time()))
        await producer.flush()
    finally:
        await producer.stop()
    return len(transactions)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Replay transactions with drift")
    parser.add_argument("--scenario", choices=SCENARIOS, required=True)
    parser.add_argument("--data", default=str(DEFAULT_SOURCE))
    parser.add_argument("--rows", type=int, default=5_000)
    parser.add_argument("--magnitude", type=float, default=1.0, help="shift in feature stds")
    parser.add_argument("--concept", type=float, default=0.6, help="share of camouflaged frauds")
    parser.add_argument("--change-at", type=float, default=0.2, help="sudden: step position")
    parser.add_argument("--incident", choices=INCIDENTS, default="missing")
    parser.add_argument("--incident-share", type=float, default=0.3)
    parser.add_argument("--fraud-rate", type=float, default=None)
    parser.add_argument("--labels-delay", type=float, default=0.0, help="seconds")
    parser.add_argument("--no-labels", action="store_true")
    parser.add_argument("--rate", type=float, default=200.0, help="transactions per second")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--out", type=Path, default=None, help="parquet file to write")
    parser.add_argument("--kafka-bootstrap", default=None, help="publish to Kafka instead")
    parser.add_argument("--topic", default="transaction.raw")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    if (args.out is None) == (args.kafka_bootstrap is None):
        parser.error("give exactly one of --out or --kafka-bootstrap")

    data, origin = load_source(args.data)
    transactions = simulate(
        data,
        args.scenario,
        rows=args.rows,
        magnitude=args.magnitude,
        concept=args.concept,
        change_at=args.change_at,
        incident=args.incident,
        incident_share=args.incident_share,
        fraud_rate=args.fraud_rate,
        labels_delay=None if args.no_labels else args.labels_delay,
        rate=args.rate,
        seed=args.seed,
    )
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        transactions.to_parquet(args.out, index=False)
        log.info(
            "wrote %d %s transactions from %s to %s",
            len(transactions),
            args.scenario,
            origin,
            args.out,
        )
    else:
        sent = asyncio.run(publish(transactions, args.kafka_bootstrap, args.topic, args.rate))
        log.info("published %d %s transactions to %s", sent, args.scenario, args.topic)


if __name__ == "__main__":
    main()
