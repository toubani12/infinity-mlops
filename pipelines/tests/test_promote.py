import json
from pathlib import Path

import pandas as pd
import pytest
from jsonschema import Draft202012Validator, FormatChecker
from mlflow import MlflowClient
from mlflow.exceptions import MlflowException

from registry import promote as promote_module
from registry import reference
from registry.promote import bootstrap_champion, promote, rollback

CONTRACTS = Path(__file__).resolve().parents[2] / "libs" / "contracts"

NAME = "fraud-xgb-promote"


@pytest.fixture(scope="module")
def registry(tracking, tmp_path_factory) -> tuple[MlflowClient, str]:
    client = MlflowClient()
    client.create_registered_model(NAME)
    source = tmp_path_factory.mktemp("model")
    for _ in range(3):
        client.create_model_version(NAME, source=source.as_uri())
    root = tmp_path_factory.mktemp("reference")
    (root / "v2").mkdir()
    pd.DataFrame({"v1": [0.1], "model_version": ["2"]}).to_parquet(
        root / "v2" / "reference.parquet"
    )
    return client, str(root)


def test_promote_requires_a_challenger(registry) -> None:
    client, root = registry
    with pytest.raises(ValueError, match="challenger"):
        promote(NAME, client=client, reference_root=root)


def test_bootstrap_then_promote_moves_champion(registry) -> None:
    client, root = registry
    first = bootstrap_champion(NAME, "1", client, root)
    assert first is not None and first.previous_version is None
    assert bootstrap_champion(NAME, "3", client, root) is None

    client.set_registered_model_alias(NAME, "challenger", "2")
    promotion = promote(NAME, client=client, reference_root=root)
    assert (promotion.version, promotion.previous_version) == ("2", "1")
    assert str(client.get_model_version_by_alias(NAME, "champion").version) == "2"
    assert pd.read_parquet(reference.current_uri(root))["model_version"].tolist() == ["2"]


def test_explicit_version_and_cli(registry, capsys, monkeypatch) -> None:
    client, root = registry
    monkeypatch.setenv("REFERENCE_ROOT", root)
    promote_module.main(["--model-name", NAME, "--version", "3"])
    out = json.loads(capsys.readouterr().out)
    assert out == {
        "model_name": NAME,
        "version": "3",
        "alias": "champion",
        "previous_version": "2",
    }
    assert pd.read_parquet(reference.current_uri(root))["model_version"].tolist() == ["2"]


ROLLBACK = "fraud-xgb-rollback"
PROMOTED = Draft202012Validator(
    json.loads((CONTRACTS / "events" / "model.promoted.v1.json").read_text()),
    format_checker=FormatChecker(),
)


@pytest.fixture
def versions(tracking, tmp_path) -> tuple[MlflowClient, str]:
    client = MlflowClient()
    name = f"{ROLLBACK}-{tmp_path.name}"
    client.create_registered_model(name)
    for _ in range(3):
        client.create_model_version(name, source=tmp_path.as_uri())
    for version in ("1", "2", "3"):
        (tmp_path / f"v{version}").mkdir()
        pd.DataFrame({"model_version": [version]}).to_parquet(
            tmp_path / f"v{version}" / "reference.parquet"
        )
    return client, name


def test_promotion_records_the_previous_champion(versions, tmp_path) -> None:
    client, name = versions
    bootstrap_champion(name, "1", client, str(tmp_path))
    promote(name, "2", client=client, reference_root=str(tmp_path))
    assert "previous_champion" not in client.get_model_version(name, "1").tags
    assert client.get_model_version(name, "2").tags["previous_champion"] == "1"


def test_rollback_returns_to_the_previous_champion(versions, tmp_path) -> None:
    client, name = versions
    root = str(tmp_path)
    bootstrap_champion(name, "1", client, root)
    promote(name, "2", client=client, reference_root=root)
    back = rollback(name, client=client, reference_root=root)
    assert (back.version, back.previous_version) == ("1", "2")
    assert str(client.get_model_version_by_alias(name, "champion").version) == "1"
    assert pd.read_parquet(reference.current_uri(root))["model_version"].tolist() == ["1"]
    assert "previous_champion" not in client.get_model_version(name, "1").tags

    event = back.event("rollback")
    PROMOTED.validate(event)
    assert event | {"event_id": "x", "timestamp": "t"} == {
        "event_id": "x",
        "timestamp": "t",
        "run_id": None,
        "model_name": name,
        "version": "1",
        "alias": "champion",
        "previous_version": "2",
        "reason": "rollback",
    }


def test_rollback_after_an_agent_promotion_needs_a_target(versions, tmp_path) -> None:
    client, name = versions
    bootstrap_champion(name, "1", client, str(tmp_path))
    client.set_registered_model_alias(name, "champion", "3")
    with pytest.raises(ValueError, match="pass the version with --to"):
        rollback(name, client=client, reference_root=str(tmp_path))
    assert rollback(name, "1", client=client, reference_root=str(tmp_path)).previous_version == "3"


def test_rollback_refuses_meaningless_moves(versions, tmp_path) -> None:
    client, name = versions
    with pytest.raises(ValueError, match="no @champion"):
        rollback(name, client=client)
    bootstrap_champion(name, "2", client, str(tmp_path))
    with pytest.raises(ValueError, match="already @champion"):
        rollback(name, "2", client=client)
    with pytest.raises(MlflowException):
        rollback(name, "9", client=client)
    assert str(client.get_model_version_by_alias(name, "champion").version) == "2"


class FakeProducer:
    def __init__(self) -> None:
        self.sent: list[tuple[str, bytes, bytes]] = []
        self.stopped = False

    async def start(self) -> None:
        pass

    async def send_and_wait(self, topic: str, value: bytes, key: bytes) -> None:
        self.sent.append((topic, value, key))

    async def stop(self) -> None:
        self.stopped = True


def test_rollback_cli_prints_and_publishes_the_event(
    versions, tmp_path, monkeypatch, capsys
) -> None:
    client, name = versions
    monkeypatch.setenv("REFERENCE_ROOT", str(tmp_path))
    bootstrap_champion(name, "2", client, str(tmp_path))
    promote(name, "3", client=client, reference_root=str(tmp_path))
    producer = FakeProducer()
    original = promote_module.publish_event

    async def publish(event, bootstrap_servers):
        await original(event, bootstrap_servers, producer)

    monkeypatch.setattr(promote_module, "publish_event", publish)
    promote_module.main(["rollback", "--model-name", name, "--kafka-bootstrap", "kafka:9092"])
    printed = json.loads(capsys.readouterr().out)
    PROMOTED.validate(printed)
    assert (printed["version"], printed["previous_version"]) == ("2", "3")
    ((topic, value, key),) = producer.sent
    assert (topic, json.loads(value), key) == ("model.promoted", printed, name.encode())
    assert producer.stopped
