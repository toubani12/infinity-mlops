import json

import pandas as pd
import pytest
from mlflow import MlflowClient

from registry import promote as promote_module
from registry import reference
from registry.promote import bootstrap_champion, promote

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
