import io
from pathlib import Path
from typing import Any

import pandas as pd


class Storage:
    """Reads and writes `s3://bucket/key` URIs through boto3, anything else as local paths."""

    def __init__(self, s3_client: Any = None, endpoint_url: str | None = None) -> None:
        self._client = s3_client
        self._endpoint_url = endpoint_url

    @property
    def s3(self) -> Any:
        if self._client is None:
            import boto3

            self._client = boto3.client("s3", endpoint_url=self._endpoint_url)
        return self._client

    @staticmethod
    def split(uri: str) -> tuple[str, str]:
        bucket, _, key = uri.removeprefix("s3://").partition("/")
        return bucket, key

    def read_bytes(self, uri: str) -> bytes:
        if uri.startswith("s3://"):
            bucket, key = self.split(uri)
            return self.s3.get_object(Bucket=bucket, Key=key)["Body"].read()
        return Path(uri).read_bytes()

    def write_bytes(self, uri: str, data: bytes) -> str:
        if uri.startswith("s3://"):
            bucket, key = self.split(uri)
            self.s3.put_object(Bucket=bucket, Key=key, Body=data)
        else:
            Path(uri).parent.mkdir(parents=True, exist_ok=True)
            Path(uri).write_bytes(data)
        return uri

    def list(self, prefix: str) -> list[str]:
        if not prefix.startswith("s3://"):
            root = Path(prefix)
            return sorted(str(p) for p in root.rglob("*") if p.is_file()) if root.exists() else []
        bucket, key = self.split(prefix)
        uris = []
        for page in self.s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=key):
            uris.extend(f"s3://{bucket}/{item['Key']}" for item in page.get("Contents", []))
        return sorted(uris)

    def read_parquet(self, uri: str) -> pd.DataFrame:
        return pd.read_parquet(io.BytesIO(self.read_bytes(uri)))
