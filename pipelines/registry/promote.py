import argparse
import json
import os
from dataclasses import asdict, dataclass

from mlflow import MlflowClient
from mlflow.exceptions import MlflowException

from registry import reference

CHAMPION = "champion"
CHALLENGER = "challenger"


@dataclass(frozen=True)
class Promotion:
    model_name: str
    version: str
    alias: str
    previous_version: str | None


def default_model_name() -> str:
    return os.environ.get("MODEL_NAME", "fraud-xgb")


def alias_version(client: MlflowClient, name: str, alias: str) -> str | None:
    try:
        return str(client.get_model_version_by_alias(name, alias).version)
    except MlflowException:
        return None


def set_alias(
    client: MlflowClient,
    name: str,
    alias: str,
    version: str,
    reference_root: str | None = None,
) -> Promotion:
    """Move the alias; a new champion also becomes the drift reference."""
    previous = alias_version(client, name, alias)
    client.set_registered_model_alias(name, alias, str(version))
    if alias == CHAMPION:
        reference.publish(str(version), reference_root)
    return Promotion(name, str(version), alias, previous)


def promote(
    name: str,
    version: str | None = None,
    *,
    alias: str = CHAMPION,
    from_alias: str = CHALLENGER,
    client: MlflowClient | None = None,
    reference_root: str | None = None,
) -> Promotion:
    """Point `alias` at `version`, or at the version behind `from_alias` when none is given."""
    client = client or MlflowClient()
    target = version or alias_version(client, name, from_alias)
    if target is None:
        raise ValueError(f"{name} has no version behind @{from_alias}")
    return set_alias(client, name, alias, target, reference_root)


def bootstrap_champion(
    name: str,
    version: str,
    client: MlflowClient | None = None,
    reference_root: str | None = None,
) -> Promotion | None:
    """Set @champion for the very first model only; later promotions go through the gate."""
    client = client or MlflowClient()
    if alias_version(client, name, CHAMPION) is not None:
        return None
    return set_alias(client, name, CHAMPION, version, reference_root)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Move a registry alias to a model version")
    parser.add_argument("--model-name", default=default_model_name())
    parser.add_argument("--version", default=None, help="defaults to the --from-alias version")
    parser.add_argument("--alias", default=CHAMPION)
    parser.add_argument("--from-alias", default=CHALLENGER)
    args = parser.parse_args(argv)
    promotion = promote(args.model_name, args.version, alias=args.alias, from_alias=args.from_alias)
    print(json.dumps(asdict(promotion)))


if __name__ == "__main__":
    main()
