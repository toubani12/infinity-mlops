# 0008. Transactional outbox for transaction.raw in the backend

Date: 2026-10-26. Status: accepted.

## Context

`POST /api/transactions` must store the transaction in PostgreSQL and publish it on `transaction.raw` for scoring. Writing to the database and sending to Kafka in the same request is a dual write: a broker outage either fails the API call or leaves a stored transaction that is never scored, and a crash between the two loses one side. Kafka transactions do not span PostgreSQL.

## Decision

The `transactions` table is its own outbox: a row is pending while `published_at` is null (migration `V2`, indexed on `published_at, received_at`). The API call only commits the row. `TransactionRawRelay` runs every 200 ms, takes up to 500 pending rows in arrival order, sends them keyed by `transaction_id`, and sets `published_at` for the rows the broker acknowledged within the send timeout. Failed or timed-out rows stay pending for the next run. Admin decisions on agent runs follow the same rule the other way round: the `agent.commands` send is acknowledged inside the database transaction, and a failed send returns 503 and changes nothing.

## Consequences

- A Kafka outage never fails `POST /api/transactions` and never loses a transaction; scoring resumes when the broker is back.
- Delivery is at least once: a crash after the ack and before the commit republishes the row. Consumers dedupe on `transaction_id` (fastapi-ml keys its output on it, the backend updates the same row).
- Scoring latency gains up to one poll interval (200 ms by default, `INFINITY_OUTBOX_POLL_INTERVAL_MS`).
- No separate outbox table or CDC tool (Debezium) to run; the cost is a polling query on an indexed column.
- `infinity_outbox_published_total` and `infinity_outbox_failed_total` show the relay on Grafana.
