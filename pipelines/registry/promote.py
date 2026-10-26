import argparse
import asyncio
import json
import os
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from mlflow import MlflowClient
from mlflow.exceptions import MlflowException

from registry import reference

CHAMPION = "champion"
CHALLENGER = "challenger"
PREVIOUS_CHAMPION_TAG = "previous_champion"


@dataclass(frozen=True)
class Promotion:
    model_name: str
    version: str
    alias: str
    previous_version: str | None

    def event(
        self, reason: Literal["promotion", "rollback"], run_id: str | None = None
    ) -> dict[str, Any]:
        return {
            "event_id": str(uuid.uuid4()),
            "timestamp": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
            "run_id": run_id,
            "model_name": self.model_name,
            "version": self.version,
            "alias": self.alias,
            "previous_version": self.previous_version,
            "reason": reason,
        }


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
    *,
    record_previous: bool = True,
) -> Promotion:
    """Move the alias; a new champion also becomes the drift reference and remembers the
    champion it replaced, which is where a rollback goes back to."""
    previous = alias_version(client, name, alias)
    client.set_registered_model_alias(name, alias, str(version))
    if alias == CHAMPION:
        if record_previous and previous is not None and previous != str(version):
            client.set_model_version_tag(name, str(version), PREVIOUS_CHAMPION_TAG, previous)
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


def rollback(
    name: str,
    to: str | None = None,
    *,
    client: MlflowClient | None = None,
    reference_root: str | None = None,
) -> Promotion:
    """Point @champion back to `to`, by default the champion recorded when the current one was
    promoted."""
    client = client or MlflowClient()
    current = alias_version(client, name, CHAMPION)
    if current is None:
        raise ValueError(f"{name} has no @{CHAMPION} to roll back")
    target = to or client.get_model_version(name, current).tags.get(PREVIOUS_CHAMPION_TAG)
    if target is None:
        raise ValueError(
            f"{name} v{current} has no {PREVIOUS_CHAMPION_TAG} tag, pass the version with --to"
        )
    if str(target) == current:
        raise ValueError(f"{name} v{current} is already @{CHAMPION}")
    client.get_model_version(name, str(target))
    return set_alias(client, name, CHAMPION, str(target), reference_root, record_previous=False)


async def publish_event(
    event: dict[str, Any], bootstrap_servers: str, producer: Any = None
) -> None:
    if producer is None:
        from aiokafka import AIOKafkaProducer

        producer = AIOKafkaProducer(bootstrap_servers=bootstrap_servers, acks="all")
    await producer.start()
    try:
        await producer.send_and_wait(
            "model.promoted", json.dumps(event).encode(), key=event["model_name"].encode()
        )
    finally:
        await producer.stop()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Move a registry alias to a model version")
    parser.add_argument("action", nargs="?", choices=("promote", "rollback"), default="promote")
    parser.add_argument("--model-name", default=default_model_name())
    parser.add_argument("--version", default=None, help="defaults to the --from-alias version")
    parser.add_argument("--alias", default=CHAMPION)
    parser.add_argument("--from-alias", default=CHALLENGER)
    parser.add_argument("--to", default=None, help="rollback target, default previous_champion")
    parser.add_argument("--kafka-bootstrap", default=None, help="also publish model.promoted")
    args = parser.parse_args(argv)
    if args.action == "promote":
        promotion = promote(
            args.model_name, args.version, alias=args.alias, from_alias=args.from_alias
        )
        print(json.dumps(asdict(promotion)))
        return
    event = rollback(args.model_name, args.to).event("rollback")
    if args.kafka_bootstrap:
        asyncio.run(publish_event(event, args.kafka_bootstrap))
    print(json.dumps(event))


if __name__ == "__main__":
    main()
