import asyncio
import time
from collections import Counter

import httpx

from app.core.config import Settings
from app.inference.model import LoadedModel
from app.main import create_app
from tests.conftest import transaction_payload


class SlowLoader:
    """Each load takes `seconds` and returns the next version; every `fail_every`-th one fails."""

    def __init__(self, predictor, seconds: float = 0.05, fail_every: int = 0) -> None:
        self.predictor = predictor
        self.seconds = seconds
        self.fail_every = fail_every
        self.calls = 0

    def load(self, name: str, alias: str) -> LoadedModel:
        self.calls += 1
        time.sleep(self.seconds)
        if self.fail_every and self.calls % self.fail_every == 0:
            raise ConnectionError("registry unreachable")
        return LoadedModel(name, str(self.calls), alias, self.predictor)


async def hammer(
    loader: SlowLoader, reloads: int, concurrency: int = 16
) -> tuple[Counter, set[str], list[int]]:
    app = create_app(Settings(), loader)
    await app.state.service.reload()
    transport = httpx.ASGITransport(app=app)
    statuses: Counter = Counter()
    reload_statuses: list[int] = []
    versions: set[str] = set()

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:

        async def reload_repeatedly() -> None:
            for _ in range(reloads):
                reload_statuses.append((await client.post("/model/reload")).status_code)

        async def predict_until(done: asyncio.Task) -> None:
            while not done.done():
                response = await client.post("/predict", json=transaction_payload())
                statuses[response.status_code] += 1
                if response.status_code == 200:
                    versions.add(response.json()["model_version"])

        reloading = asyncio.create_task(reload_repeatedly())
        await asyncio.gather(*(predict_until(reloading) for _ in range(concurrency)), reloading)
    return statuses, versions, reload_statuses


def test_predict_never_fails_while_the_model_is_swapped(predictor) -> None:
    statuses, versions, reloads = asyncio.run(hammer(SlowLoader(predictor), reloads=5))
    assert set(statuses) == {200}
    assert statuses[200] > 0
    assert len(versions) >= 2
    assert reloads == [200] * 5


def test_failed_reloads_do_not_interrupt_predictions(predictor) -> None:
    statuses, _, reloads = asyncio.run(hammer(SlowLoader(predictor, fail_every=2), reloads=6))
    assert set(statuses) == {200}
    assert reloads.count(503) == 3 and reloads.count(200) == 3
