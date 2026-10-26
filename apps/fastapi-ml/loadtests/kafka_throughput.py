"""Publish transaction.raw messages and measure how fast transaction.scored comes back."""

import argparse
import asyncio
import json
import statistics
import time
import uuid

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

from loadtests.locustfile import payload


def raw_event(sent_at: float) -> dict:
    body = payload()
    return {
        "transaction_id": body["transaction_id"],
        "timestamp": body["timestamp"],
        "amount": body["amount"],
        **body["features"],
        "_sent_at": sent_at,
    }


async def run(bootstrap: str, messages: int, rate: float) -> dict:
    sent: dict[str, float] = {}
    latencies: list[float] = []
    consumer = AIOKafkaConsumer(
        "transaction.scored",
        bootstrap_servers=bootstrap,
        group_id=f"loadtest-{uuid.uuid4().hex[:8]}",
        auto_offset_reset="latest",
    )
    producer = AIOKafkaProducer(bootstrap_servers=bootstrap, linger_ms=5)
    await consumer.start()
    await producer.start()
    await asyncio.sleep(2)

    async def collect() -> None:
        async for record in consumer:
            event = json.loads(record.value)
            started = sent.pop(event["transaction_id"], None)
            if started is not None:
                latencies.append((time.perf_counter() - started) * 1000)
                if len(latencies) == messages:
                    return

    collector = asyncio.create_task(collect())
    begin = time.perf_counter()
    for i in range(messages):
        delay = begin + i / rate - time.perf_counter()
        if delay > 0:
            await asyncio.sleep(delay)
        now = time.perf_counter()
        event = raw_event(now)
        event.pop("_sent_at")
        sent[event["transaction_id"]] = now
        await producer.send(
            "transaction.raw", json.dumps(event).encode(), key=event["transaction_id"].encode()
        )
    await producer.flush()
    try:
        await asyncio.wait_for(collector, timeout=60)
    except TimeoutError:
        pass
    elapsed = time.perf_counter() - begin
    await producer.stop()
    await consumer.stop()
    ordered = sorted(latencies)
    return {
        "sent": messages,
        "scored": len(latencies),
        "lost": messages - len(latencies),
        "throughput_per_s": round(len(latencies) / elapsed, 1),
        "p50_ms": round(statistics.median(ordered), 1) if ordered else None,
        "p95_ms": round(ordered[int(0.95 * (len(ordered) - 1))], 1) if ordered else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bootstrap", default="localhost:9092")
    parser.add_argument("--messages", type=int, default=12_000)
    parser.add_argument("--rate", type=float, default=200.0)
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(args.bootstrap, args.messages, args.rate))))


if __name__ == "__main__":
    main()
