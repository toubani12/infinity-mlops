# backend-spring

Business entry point of Infinity MLOps. It stores incoming transactions, serves them to the dashboard and keeps the fraud alerts raised from the model scores.

Spring Boot 3.5, Java 21, PostgreSQL with Flyway, Actuator with Prometheus metrics.

## API

| Method | Path | Notes |
|---|---|---|
| POST | `/api/transactions` | body `{ transactionId?, timestamp?, amount, features: { v1..v28 }, label? }`, returns 201 |
| GET | `/api/transactions/{id}` | |
| GET | `/api/transactions?page&size&fraudOnly` | newest first, `size` ≤ 200 |
| GET | `/api/alerts?page&size&status` | `status` in `OPEN`, `ACKNOWLEDGED`, `CLOSED` |
| PATCH | `/api/alerts/{id}` | body `{ "status": "ACKNOWLEDGED" }` |
| GET | `/api/drift/reports?page&size` and `/api/drift/reports/{id}` | from `drift.detected`, newest first |
| GET | `/api/models/versions?page&size` | champion alias moves from `model.promoted`, newest first |
| GET | `/api/stream/transactions` | SSE, event `transaction` (same JSON as the REST transaction) after each score |
| GET | `/api/stream/alerts` | SSE, event `alert` when an alert opens or changes status |
| GET | `/api/agent/runs?page&size&status` | agent runs, newest first |
| GET | `/api/agent/runs/{runId}` | `{ run, champion, challenger, gate, events }` |
| POST | `/api/agent/runs/{runId}/approve` | admin only, publishes `agent.commands` |
| POST | `/api/agent/runs/{runId}/reject` | admin only, body `{ "reason": "..." }` (3 to 500 characters after trimming) |
| GET | `/api/stream/agent` | SSE, event `agent` with `{ run, event }` on each step and when a decision is sent |
| GET | `/actuator/health`, `/actuator/prometheus` | |

REST bodies use camelCase. Kafka payloads follow `libs/contracts` (snake_case). Lists return `{ content, page, size, totalElements, totalPages }`. Errors are RFC 9457 problem details (`application/problem+json`); validation errors add an `errors` map keyed by field.

The server generates `transactionId` and `timestamp` when they are absent; a duplicate `transactionId` returns 409. Alert status only moves forward (`OPEN` → `ACKNOWLEDGED` → `CLOSED`); going back returns 409.

Streams are fed after the database commit (`@TransactionalEventListener`) by an in-memory broadcaster: one sender thread keeps event order and isolates the Kafka consumer from slow clients, a comment heartbeat goes out every 15 s, each stream closes after 30 min and announces `retry: 3000`. The broadcaster is per instance, so with several replicas the ingress needs sticky sessions or each replica must consume with its own group. Connected clients: `infinity_sse_clients{channel}`.

## Security

Every `/api/**` route needs a bearer JWT signed with HS256 and `JWT_SECRET` (at least 32 bytes, the service refuses to start otherwise). Roles come from the `roles` claim: `analyst` reads and updates the API, `admin` implies `analyst` and will also approve agent runs. Missing, forged or expired tokens get 401, tokens without a known role get 403. `/actuator/health/**` and `/actuator/prometheus` stay public.

Under the `local` profile only, `POST /api/auth/dev-token` with `{ "username": "ana", "role": "analyst" }` returns `{ token, expiresAt }` (8 h). SSE routes under `/api/stream/` also accept the token as `?access_token=` because `EventSource` cannot send headers; other routes ignore that parameter. CORS allows `CORS_ALLOWED_ORIGINS` (comma separated, default `http://localhost:3000`).

```bash
TOKEN=$(curl -s -X POST localhost:8080/api/auth/dev-token -H 'Content-Type: application/json' \
  -d '{"username":"ana","role":"analyst"}' | jq -r .token)
curl -H "Authorization: Bearer $TOKEN" localhost:8080/api/alerts
```

## Storage

`transactions.features` is a single `double precision[]` column of 28 values in `v1`..`v28` order, with a `CHECK (cardinality(features) = 28)`. The vector is always read and written as a whole, never queried per feature, so one array column keeps the row compact (no 28 columns, no JSONB key overhead) and maps directly to the model input order. The JSON map form is rebuilt at the API boundary (`Features`).

`received_at` is set by the server and drives the default ordering, so replayed transactions with old `timestamp` values still show up first in the live views. Scoring fields (`fraud_score`, `is_fraud`, `model_version`, `scored_at`) stay null until `transaction.scored` arrives.

## Messaging

Accepted transactions are published to `transaction.raw`, key `transaction_id`, value exactly the v1 contract (`transaction_id`, `timestamp`, `amount`, `v1`..`v28`, plus `label` when known).

The `transactions` table is its own outbox. `POST /api/transactions` only commits the row; `TransactionRawRelay` runs every 200 ms, takes up to 500 rows with `published_at IS NULL` in arrival order, sends them and sets `published_at` for the ones the broker acknowledged. A row whose send fails or times out stays pending and is retried on the next run, so a Kafka outage never loses a transaction and never fails the API call. Delivery is at least once (a crash after the ack and before the commit republishes the row); consumers dedupe on `transaction_id`. Metrics: `infinity_outbox_published_total` and `infinity_outbox_failed_total`.

The service also consumes `drift.detected` into `drift_report` and `model.promoted` into `model_version_event`, both idempotent on the event id (`report_id`, `event_id`).

It consumes `transaction.scored` in group `backend-spring`. Each record updates the transaction's score fields and opens an alert when `fraud_score >= ALERT_THRESHOLD`. Replays are harmless: the score is overwritten with the same values and `alerts.transaction_id` is unique, checked before insert. Scores for unknown transactions are logged and counted (`infinity_scores_unknown_transaction_total`), so transactions must enter through `POST /api/transactions` to appear in the dashboard. Unreadable or incomplete records are skipped at once; other failures are retried three times one second apart, then logged and skipped.

## Agent runs

`agent.events` is consumed into `agent_run` (one row per run) and `agent_run_event` (the timeline, ordered by arrival through `seq`), idempotent on `event_id`. The run status follows the steps listed in `services/agents-langgraph/README.md`:

| Status | Set by |
|---|---|
| `RUNNING` | first event, and `approved` while the promotion runs |
| `AWAITING_APPROVAL` | `approval_requested` |
| `PROMOTED` | `promoted` or `completed` (promote) |
| `REJECTED` | `rejected` |
| `KEPT_CHAMPION` | `completed` (keep_champion) after a failed gate |
| `ESCALATED` | `escalated` or `completed` (data_incident) |
| `FAILED` | `failed` |
| `NOISE` | `completed` (noise) |

A final status never changes, so the `completed` that follows `rejected` and a `received` for an alert attached to the run leave it as is. Champion and challenger metrics come from the `evaluated` and `approval_requested` payloads, the gate result and reasons from `evaluated`; the detail also returns `gate.maxP95LatencyMs` (`MAX_P95_LATENCY_MS`, same default as the agent).

Approve and reject need the `admin` role and answer 409 unless the run is `AWAITING_APPROVAL` with no decision sent yet. The command (`run_id`, `command_id`, `timestamp`, `action`, `actor` = JWT subject, `reason`) is sent keyed by `run_id` and acknowledged by the broker inside the database transaction: the run keeps it as `pendingCommand` until the agent answers with `approved` or `rejected`, and a failed send returns 503 and changes nothing. Two admins deciding at the same time are serialized by the row version, the second one gets 409.

## Configuration

| Variable | Default |
|---|---|
| `SPRING_DATASOURCE_URL` | `jdbc:postgresql://localhost:5432/infinity` |
| `SPRING_DATASOURCE_USERNAME` / `SPRING_DATASOURCE_PASSWORD` | `infinity` / `infinity` |
| `KAFKA_BOOTSTRAP_SERVERS` | `localhost:9092` |
| `ALERT_THRESHOLD` | `0.5` |
| `MAX_P95_LATENCY_MS` | `50` |
| `JWT_SECRET` | none, required |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:3000` |
| `SPRING_PROFILES_ACTIVE` | set `local` to enable the dev token endpoint |
| `INFINITY_OUTBOX_ENABLED` / `INFINITY_OUTBOX_POLL_INTERVAL_MS` / `INFINITY_OUTBOX_BATCH_SIZE` | `true` / `200` / `500` |

## Run and test

```bash
JWT_SECRET=local-dev-secret-change-me-0123456789abcdef \
  mvn spring-boot:run -Dspring-boot.run.profiles=local   # needs the stack of infra/docker-compose.yml
mvn -B verify                                   # every test, JaCoCo report in target/site/jacoco
mvn -B verify -DexcludedGroups=integration      # skip the Testcontainers suite for a fast loop
mvn -B verify -Dgroups=integration              # only the Testcontainers suite
docker build -t backend-spring .
```

`PlatformFlowIntegrationTest` (tag `integration`) starts `postgres:16-alpine` and `apache/kafka:3.9.1`, the images of `infra/docker-compose.yml`, and checks the whole path on real infrastructure: Flyway on PostgreSQL, `POST /api/transactions` through the outbox to `transaction.raw`, `transaction.scored` to an open alert, `agent.events` to a run awaiting approval, and an admin approval to `agent.commands`, every message validated against `libs/contracts`. It needs a Docker daemon: without one the class is reported as skipped (`@Testcontainers(disabledWithoutDocker = true)`), so the build still passes on machines without Docker. GitHub runners have Docker, so CI runs it as part of `mvn -B verify`.

The other tests need no Docker. The migrations only use SQL accepted by both PostgreSQL and H2, so the `@DataJpaTest` slices run the real Flyway scripts without Docker. The messaging tests validate payloads against `../../libs/contracts/events` (override with `-Dcontracts.dir=...`), so run them from a full checkout.
