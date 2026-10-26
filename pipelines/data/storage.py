import io
import os
from pathlib import Path
from typing import Any

import pandas as pd


def is_s3(uri: str) -> bool:
    return uri.startswith("s3://")


def split_s3_uri(uri: str) -> tuple[str, str]:
    bucket, _, key = uri.removeprefix("s3://").partition("/")
    if not bucket or not key:
        raise ValueError(f"invalid s3 uri: {uri}")
    return bucket, key


def list_files(prefix: str, suffix: str = ".parquet", client: Any = None) -> list[str]:
    """Every file under a local folder or an s3:// prefix, sorted, filtered by suffix."""
    if not is_s3(prefix):
        return sorted(str(path) for path in Path(prefix).rglob(f"*{suffix}") if path.is_file())
    bucket, _, key_prefix = prefix.removeprefix("s3://").partition("/")
    client = client or s3_client()
    keys: list[str] = []
    request = {"Bucket": bucket, "Prefix": key_prefix}
    while True:
        page = client.list_objects_v2(**request)
        keys += [item["Key"] for item in page.get("Contents", []) if item["Key"].endswith(suffix)]
        if not page.get("IsTruncated"):
            return sorted(f"s3://{bucket}/{key}" for key in keys)
        request["ContinuationToken"] = page["NextContinuationToken"]


def s3_endpoint() -> str | None:
    return os.environ.get("S3_ENDPOINT_URL") or os.environ.get("MLFLOW_S3_ENDPOINT_URL")


def s3_client(endpoint_url: str | None = None) -> Any:
    import boto3

    return boto3.client("s3", endpoint_url=endpoint_url or s3_endpoint())


def read_table(uri: str, client: Any = None) -> pd.DataFrame:
    suffix = Path(split_s3_uri(uri)[1] if is_s3(uri) else uri).suffix.lower()
    if suffix not in {".csv", ".parquet"}:
        raise ValueError(f"unsupported file type: {uri}")
    source: Any = Path(uri)
    if is_s3(uri):
        bucket, key = split_s3_uri(uri)
        body = (client or s3_client()).get_object(Bucket=bucket, Key=key)["Body"].read()
        source = io.BytesIO(body)
    return pd.read_csv(source) if suffix == ".csv" else pd.read_parquet(source)


def write_parquet(df: pd.DataFrame, uri: str, client: Any = None) -> str:
    if is_s3(uri):
        buffer = io.BytesIO()
        df.to_parquet(buffer, index=False)
        bucket, key = split_s3_uri(uri)
        (client or s3_client()).put_object(Bucket=bucket, Key=key, Body=buffer.getvalue())
        return uri
    path = Path(uri)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)
    return str(path)
