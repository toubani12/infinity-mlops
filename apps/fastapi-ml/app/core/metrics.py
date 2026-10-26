from prometheus_client import Counter, Histogram

REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency",
    ["method", "path", "status"],
    buckets=(0.001, 0.0025, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5),
)
PREDICTIONS = Counter(
    "predictions_total", "Scored transactions", ["source", "outcome", "model_version"]
)
FRAUD_SCORE = Histogram(
    "fraud_score", "Fraud score distribution", buckets=tuple(i / 10 for i in range(1, 11))
)
MODEL_RELOADS = Counter("model_reloads_total", "Model reload attempts", ["result"])
KAFKA_MESSAGES = Counter("kafka_messages_total", "Consumed transaction.raw messages", ["result"])
KAFKA_BATCH_SIZE = Histogram(
    "kafka_batch_size", "Messages scored per batch", buckets=(1, 2, 4, 8, 16, 32, 64, 128, 256)
)
PREDICTION_LOG_ROWS = Counter(
    "prediction_log_rows_total", "Prediction log rows by outcome", ["result"]
)
