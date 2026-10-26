# 0002. Kafka in KRaft mode

Date: 2026-10-26. Status: accepted.

## Context

Services communicate through six topics, and the demo replays a topic to simulate drift. The bus must start quickly on a 16 GB laptop and in a CI kind cluster. Classic Kafka needs a ZooKeeper ensemble next to the brokers, and Kafka 4 removes ZooKeeper support.

## Decision

Run Kafka in KRaft mode with the official `apache/kafka` image: one node acting as broker and controller, locally and on minikube. Topics are created explicitly by an init container (auto-creation is disabled), keyed by `transaction_id`, `run_id`, `report_id` or `model_name`, with 7 days retention for `transaction.*` and 30 days for the others. Values are JSON validated against `libs/contracts`, without a schema registry.

## Consequences

- One container instead of two, and no ZooKeeper to monitor or upgrade.
- Replication factor 1: losing the broker volume loses the topics. Acceptable for local and demo environments, not for production.
- Without a schema registry, compatibility is enforced by contract tests and the `.vN` file convention rather than at produce time.
- Topic settings live in `infra/kafka/create-topics.sh` and its Kubernetes counterpart; both must change together.
