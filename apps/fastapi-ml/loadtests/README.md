# Load tests

Two scenarios, both against a running fastapi-ml with a real `@champion` loaded.

## /predict with Locust

```bash
uv sync --group load
uv run --group load locust -f loadtests/locustfile.py --host http://localhost:8000 \
  --headless --users 50 --spawn-rate 10 --run-time 60s --csv loadtests/results/predict
```

Payloads draw the V features from normal distributions with the spread of the ULB components
and amounts from a log-normal, with 0.2 % fraud-like rows. Target from the sprint 4 Definition
of Done: p95 under 50 ms at 200 requests/s.

## Kafka scoring throughput

```bash
uv run python -m loadtests.kafka_throughput --bootstrap localhost:9092 --messages 12000 --rate 200
```

Publishes `transaction.raw` events at a fixed rate, reads `transaction.scored`, and prints
throughput, lost messages and end-to-end p50/p95 latency. Run it with `KAFKA_BATCH_SIZE` and
`KAFKA_MAX_WAIT_MS` set on the service to compare batch settings. Transactions published here
bypass the backend, so they are scored but do not appear on the dashboard.
