from types import SimpleNamespace

from monitor.reference import resolve_reference_uri

FALLBACK = "s3://datasets/reference/reference.parquet"


class FakeClient:
    def __init__(self, version=None, error=None):
        self.version, self.error, self.calls = version, error, []

    def get_model_version_by_alias(self, name, alias):
        self.calls.append((name, alias))
        if self.error:
            raise self.error
        return self.version


def test_explicit_uri_skips_the_registry() -> None:
    client = FakeClient()
    uri = resolve_reference_uri("/tmp/ref.parquet", FALLBACK, "fraud-xgb", lambda: client)
    assert uri == "/tmp/ref.parquet"
    assert client.calls == []


def test_auto_follows_the_champion_tag() -> None:
    version = SimpleNamespace(
        version="7", tags={"reference_uri": "s3://datasets/reference/v7/reference.parquet"}
    )
    client = FakeClient(version)
    uri = resolve_reference_uri("auto", FALLBACK, "fraud-xgb", lambda: client)
    assert uri == "s3://datasets/reference/v7/reference.parquet"
    assert client.calls == [("fraud-xgb", "champion")]


def test_auto_falls_back_without_tag() -> None:
    version = SimpleNamespace(version="2", tags={})
    assert (
        resolve_reference_uri("auto", FALLBACK, "fraud-xgb", lambda: FakeClient(version))
        == FALLBACK
    )


def test_auto_falls_back_when_registry_fails() -> None:
    client = FakeClient(error=RuntimeError("connection refused"))
    assert resolve_reference_uri("auto", FALLBACK, "fraud-xgb", lambda: client) == FALLBACK
