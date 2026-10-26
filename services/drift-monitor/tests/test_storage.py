import io

import pandas as pd

from monitor.storage import Storage


class FakeS3:
    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], bytes] = {}

    def put_object(self, Bucket, Key, Body) -> None:
        self.objects[(Bucket, Key)] = Body

    def get_object(self, Bucket, Key) -> dict:
        return {"Body": io.BytesIO(self.objects[(Bucket, Key)])}

    def get_paginator(self, name):
        objects = self.objects

        class Paginator:
            def paginate(self, Bucket, Prefix):
                keys = [k for b, k in objects if b == Bucket and k.startswith(Prefix)]
                yield {"Contents": [{"Key": k} for k in keys]}

        return Paginator()


def test_s3_round_trip_and_listing() -> None:
    storage = Storage(FakeS3())
    buffer = io.BytesIO()
    pd.DataFrame({"v1": [1.0]}).to_parquet(buffer)
    storage.write_bytes("s3://predictions/dt=2026-10-26/hour=10/part-a.parquet", buffer.getvalue())
    storage.write_bytes("s3://predictions/dt=2026-10-26/hour=11/part-b.parquet", b"x")
    listed = storage.list("s3://predictions/dt=2026-10-26/hour=10/")
    assert listed == ["s3://predictions/dt=2026-10-26/hour=10/part-a.parquet"]
    assert storage.read_parquet(listed[0])["v1"].tolist() == [1.0]


def test_local_round_trip(tmp_path) -> None:
    storage = Storage()
    target = str(tmp_path / "a" / "b.json")
    storage.write_bytes(target, b"{}")
    assert storage.read_bytes(target) == b"{}"
    assert storage.list(str(tmp_path)) == [target]
    assert storage.list(str(tmp_path / "missing")) == []


def test_lazy_boto3_client() -> None:
    storage = Storage(endpoint_url="http://minio:9000")
    assert storage.s3.meta.endpoint_url == "http://minio:9000"
