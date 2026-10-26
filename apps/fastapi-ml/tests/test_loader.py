import mlflow
import mlflow.xgboost
import pytest
from mlflow import MlflowClient

from app.inference.model import FEATURES, MlflowModelLoader
from tests.conftest import synthetic_frame


@pytest.fixture(scope="module")
def registry(tmp_path_factory, predictor) -> str:
    tmp_path = tmp_path_factory.mktemp("registry")
    uri = f"sqlite:///{tmp_path / 'mlflow.db'}"
    mlflow.set_tracking_uri(uri)
    experiment = mlflow.create_experiment("loader", artifact_location=(tmp_path / "a").as_uri())
    with mlflow.start_run(experiment_id=experiment):
        for _ in range(2):
            mlflow.xgboost.log_model(predictor, name="model", registered_model_name="fraud-xgb")
    MlflowClient().set_registered_model_alias("fraud-xgb", "champion", "2")
    return uri


def test_loads_the_version_behind_the_alias(registry) -> None:
    loaded = MlflowModelLoader(registry).load("fraud-xgb", "champion")
    assert (loaded.name, loaded.version, loaded.alias) == ("fraud-xgb", "2", "champion")
    scores = loaded.predictor.predict_proba(synthetic_frame(5)[FEATURES])
    assert scores.shape == (5, 2)


def test_unknown_alias_raises(registry) -> None:
    with pytest.raises(mlflow.exceptions.MlflowException):
        MlflowModelLoader(registry).load("fraud-xgb", "challenger")
