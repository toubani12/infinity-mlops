#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["httpx>=0.28", "pandas>=2.2", "pyarrow>=18"]
# ///
"""Send transactions to backend-spring at a fixed rate.

Sources: the ULB CSV (`data/creditcard.csv`), its parquet, or a replay file written by
`pipelines/data/simulate_drift.py --out`. Everything goes through POST /api/transactions so
the rows exist in the backend before they are scored.
"""

import argparse
import asyncio
import math
import random
import sys
import time
from collections import Counter
from pathlib import Path

import httpx
import pandas as pd

FEATURES = [f"v{i}" for i in range(1, 29)]


def load(path: Path, rows: int | None, fraud_share: float | None, seed: int) -> pd.DataFrame:
    frame = pd.read_parquet(path) if path.suffix == ".parquet" else pd.read_csv(path)
    frame.columns = [c.lower() for c in frame.columns]
    missing = [c for c in [*FEATURES, "amount"] if c not in frame.columns]
    if missing:
        sys.exit(f"{path}: missing columns {missing}")
    if "label" not in frame.columns and "class" in frame.columns:
        frame["label"] = frame["class"]
    if fraud_share is not None and "label" in frame.columns and rows:
        frauds = frame[frame["label"] == 1]
        legit = frame[frame["label"] == 0]
        n_fraud = min(len(frauds), round(rows * fraud_share))
        frame = pd.concat(
            [
                frauds.sample(n_fraud, random_state=seed),
                legit.sample(rows - n_fraud, random_state=seed),
            ]
        ).sample(frac=1, random_state=seed)
    elif rows:
        frame = frame.sample(min(rows, len(frame)), random_state=seed)
    return frame.reset_index(drop=True)


def body(row: pd.Series, with_labels: bool) -> dict:
    payload = {
        "amount": float(row["amount"]),
        "features": {f: float(row[f]) for f in FEATURES if not pd.isna(row[f])},
    }
    if "transaction_id" in row and isinstance(row["transaction_id"], str):
        payload["transactionId"] = row["transaction_id"]
    if with_labels and "label" in row and not pd.isna(row["label"]):
        payload["label"] = int(row["label"])
    return payload


async def token(client: httpx.AsyncClient, username: str) -> str:
    response = await client.post(
        "/api/auth/dev-token", json={"username": username, "role": "analyst"}
    )
    response.raise_for_status()
    return response.json()["token"]


async def send(args: argparse.Namespace, frame: pd.DataFrame) -> Counter:
    results: Counter = Counter()
    queue: asyncio.Queue = asyncio.Queue(maxsize=args.concurrency * 4)
    async with httpx.AsyncClient(base_url=args.api, timeout=10) as client:
        client.headers["Authorization"] = f"Bearer {await token(client, args.username)}"

        async def worker() -> None:
            while (payload := await queue.get()) is not None:
                try:
                    response = await client.post("/api/transactions", json=payload)
                    results[response.status_code] += 1
                except httpx.HTTPError as exc:
                    results[type(exc).__name__] += 1

        workers = [asyncio.create_task(worker()) for _ in range(args.concurrency)]
        started = time.monotonic()
        for i, (_, row) in enumerate(frame.iterrows()):
            delay = started + i / args.rate - time.monotonic()
            if delay > 0:
                await asyncio.sleep(delay)
            await queue.put(body(row, not args.no_labels))
            if (i + 1) % max(1, math.ceil(args.rate * 10)) == 0:
                print(f"{i + 1}/{len(frame)} sent, {dict(results)}", flush=True)
        for _ in workers:
            await queue.put(None)
        await asyncio.gather(*workers)
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", type=Path, default=Path("data/creditcard.csv"))
    parser.add_argument("--rows", type=int, default=2000)
    parser.add_argument("--fraud-share", type=float, default=None, help="oversample frauds")
    parser.add_argument("--rate", type=float, default=50.0, help="transactions per second")
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--api", default="http://localhost:8080")
    parser.add_argument("--username", default="seed")
    parser.add_argument("--no-labels", action="store_true", help="do not send ground truth")
    parser.add_argument("--seed", type=int, default=random.randrange(1 << 16))
    args = parser.parse_args()
    if not args.data.exists():
        sys.exit(f"{args.data} not found: download the ULB dataset or pass --data")
    frame = load(args.data, args.rows, args.fraud_share, args.seed)
    print(f"sending {len(frame)} transactions from {args.data} at {args.rate}/s to {args.api}")
    results = asyncio.run(send(args, frame))
    print(f"done: {dict(results)}")
    if set(results) - {201, 200}:
        sys.exit(1)


if __name__ == "__main__":
    main()
