#!/usr/bin/env bash
set -euo pipefail

bootstrap="${KAFKA_BOOTSTRAP_SERVERS:-kafka:29092}"
bin=/opt/kafka/bin
seven_days_ms=604800000
thirty_days_ms=2592000000

# topic:partitions:retention_ms
topics=(
  "transaction.raw:6:${seven_days_ms}"
  "transaction.scored:6:${seven_days_ms}"
  "drift.detected:1:${thirty_days_ms}"
  "agent.events:3:${thirty_days_ms}"
  "agent.commands:3:${thirty_days_ms}"
  "model.promoted:1:${thirty_days_ms}"
)

for spec in "${topics[@]}"; do
  IFS=: read -r name partitions retention <<< "$spec"
  "$bin/kafka-topics.sh" --bootstrap-server "$bootstrap" --create --if-not-exists \
    --topic "$name" --partitions "$partitions" --replication-factor 1 \
    --config "retention.ms=$retention"
  # --if-not-exists leaves an existing topic untouched, so retention is re-applied explicitly.
  "$bin/kafka-configs.sh" --bootstrap-server "$bootstrap" --alter \
    --entity-type topics --entity-name "$name" --add-config "retention.ms=$retention" > /dev/null
done

"$bin/kafka-topics.sh" --bootstrap-server "$bootstrap" --list
