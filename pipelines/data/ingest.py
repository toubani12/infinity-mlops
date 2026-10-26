import argparse
import json
import logging
from pathlib import Path
from typing import Any

import pandas as pd

from data import synthetic
from data.schema import FEATURES, RAW_COLUMNS, TARGET, TIME
from data.storage import is_s3, read_table, s3_endpoint, write_parquet
from data.validate import ValidationReport, validate

log = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
DEFAULT_SOURCE = DATA_DIR / "creditcard.csv"
S3_DESTINATION = "s3://datasets/raw/creditcard.parquet"
LOCAL_DESTINATION = DATA_DIR / "raw" / "creditcard.parquet"


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    return df.rename(columns=lambda c: str(c).strip().strip('"').lower())


def load_source(
    source: str | Path = DEFAULT_SOURCE,
    *,
    synthetic_rows: int = synthetic.REAL_ROWS,
    fraud_rate: float = synthetic.REAL_FRAUD_RATE,
    seed: int = 42,
    client: Any = None,
) -> tuple[pd.DataFrame, str]:
    """Read the real dataset, or fall back to synthetic data when the local file is absent."""
    uri = str(source)
    if is_s3(uri) or Path(uri).exists():
        return normalize_columns(read_table(uri, client)), uri
    log.warning("%s not found, generating %d synthetic rows", uri, synthetic_rows)
    frame = synthetic.generate(synthetic_rows, fraud_rate, seed)
    return normalize_columns(frame), "synthetic"


def prepare(df: pd.DataFrame) -> pd.DataFrame:
    out = df[RAW_COLUMNS].astype({c: "float64" for c in [TIME, *FEATURES]})
    out[TARGET] = out[TARGET].astype("int64")
    return out.sort_values(TIME, kind="stable").reset_index(drop=True)


def ingest(
    source: str | Path, destination: str, *, client: Any = None, **synthetic_options: Any
) -> ValidationReport:
    df, origin = load_source(source, client=client, **synthetic_options)
    report = validate(df)
    write_parquet(prepare(df), destination, client)
    log.info("ingested %d rows from %s into %s", report.rows, origin, destination)
    return report


def default_destination() -> str:
    return S3_DESTINATION if s3_endpoint() else str(LOCAL_DESTINATION)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Ingest the credit card CSV into parquet")
    parser.add_argument("--src", default=str(DEFAULT_SOURCE))
    parser.add_argument("--dest", default=None, help="local path or s3://bucket/key")
    parser.add_argument("--synthetic-rows", type=int, default=synthetic.REAL_ROWS)
    parser.add_argument("--fraud-rate", type=float, default=synthetic.REAL_FRAUD_RATE)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")

    report = ingest(
        args.src,
        args.dest or default_destination(),
        synthetic_rows=args.synthetic_rows,
        fraud_rate=args.fraud_rate,
    )
    print(json.dumps(report.to_dict(), indent=2))


if __name__ == "__main__":
    main()
