import io
import json

import pandas as pd

from data import ingest as ingest_module
from data.ingest import ingest, load_source, normalize_columns
from data.schema import RAW_COLUMNS
from data.storage import read_table, split_s3_uri, write_parquet
from data.synthetic import generate


class FakeS3:
    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], bytes] = {}

    def put_object(self, Bucket: str, Key: str, Body: bytes) -> None:
        self.objects[(Bucket, Key)] = Body

    def get_object(self, Bucket: str, Key: str) -> dict:
        return {"Body": io.BytesIO(self.objects[(Bucket, Key)])}


def test_normalize_columns() -> None:
    frame = pd.DataFrame(columns=[' "Time"', "V1", "Amount ", "Class"])
    assert list(normalize_columns(frame).columns) == ["time", "v1", "amount", "class"]


def test_ingest_csv_to_local_parquet(tmp_path) -> None:
    csv = tmp_path / "creditcard.csv"
    generate(rows=300, fraud_rate=0.05, seed=1).sample(frac=1, random_state=0).to_csv(
        csv, index=False
    )
    report = ingest(csv, str(tmp_path / "out" / "raw.parquet"))
    out = pd.read_parquet(tmp_path / "out" / "raw.parquet")
    assert report.ok and report.frauds == 15
    assert list(out.columns) == RAW_COLUMNS
    assert out["time"].is_monotonic_increasing
    assert out["class"].dtype == "int64"


def test_ingest_falls_back_to_synthetic_and_writes_s3(tmp_path) -> None:
    s3 = FakeS3()
    report = ingest(
        tmp_path / "absent.csv",
        "s3://datasets/raw/creditcard.parquet",
        client=s3,
        synthetic_rows=500,
        fraud_rate=0.02,
    )
    assert report.rows == 500
    stored = read_table("s3://datasets/raw/creditcard.parquet", client=s3)
    assert len(stored) == 500 and stored["class"].sum() == 10


def test_load_source_reads_parquet_from_s3() -> None:
    s3 = FakeS3()
    write_parquet(generate(rows=50, seed=2), "s3://datasets/raw/x.parquet", client=s3)
    frame, origin = load_source("s3://datasets/raw/x.parquet", client=s3)
    assert origin == "s3://datasets/raw/x.parquet"
    assert "v28" in frame.columns


def test_split_s3_uri() -> None:
    assert split_s3_uri("s3://datasets/reference/reference.parquet") == (
        "datasets",
        "reference/reference.parquet",
    )


def test_cli_prints_report(tmp_path, capsys, monkeypatch) -> None:
    monkeypatch.delenv("S3_ENDPOINT_URL", raising=False)
    monkeypatch.delenv("MLFLOW_S3_ENDPOINT_URL", raising=False)
    monkeypatch.setattr(ingest_module, "LOCAL_DESTINATION", tmp_path / "raw.parquet")
    ingest_module.main(["--src", str(tmp_path / "none.csv"), "--synthetic-rows", "200"])
    assert json.loads(capsys.readouterr().out)["rows"] == 200
    assert (tmp_path / "raw.parquet").exists()
