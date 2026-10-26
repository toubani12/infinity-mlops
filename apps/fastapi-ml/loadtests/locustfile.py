import random
import uuid
from datetime import UTC, datetime

from locust import FastHttpUser, between, task

FEATURES = [f"v{i}" for i in range(1, 29)]
# Standard deviations of the PCA components decrease with their rank in the ULB data.
SCALES = [1.9 - i * 0.06 for i in range(28)]


def payload(fraud_share: float = 0.002) -> dict:
    fraud = random.random() < fraud_share
    features = {
        name: random.gauss(0.0, scale) for name, scale in zip(FEATURES, SCALES, strict=True)
    }
    if fraud:
        features |= {
            "v14": random.gauss(-7, 2),
            "v12": random.gauss(-6, 2),
            "v10": random.gauss(-5, 2),
        }
    return {
        "transaction_id": str(uuid.uuid4()),
        "timestamp": datetime.now(UTC).isoformat(),
        "amount": round(random.lognormvariate(3.5, 1.2), 2),
        "features": features,
    }


class Scorer(FastHttpUser):
    wait_time = between(0.0, 0.01)

    @task
    def predict(self) -> None:
        with self.client.post("/predict", json=payload(), catch_response=True) as response:
            if response.status_code != 200:
                response.failure(f"status {response.status_code}")
