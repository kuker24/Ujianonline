#!/usr/bin/env python3
"""Safe mobile-first answer-sync smoke/load helper.

This script is intentionally staging-first. By default it prints the planned
traffic only (--dry-run). To send traffic, pass --execute and provide staging
session/question IDs created for test data.
"""

from __future__ import annotations

import argparse
import asyncio
import random
import statistics
import time
from dataclasses import dataclass
from typing import Iterable
from urllib.parse import urlparse

import httpx

PRODUCTION_HOSTS = {"man1rokanhulu.cloud", "103.175.218.56"}


@dataclass
class Sample:
    endpoint: str
    status_code: int
    latency_ms: float
    ok: bool


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    sorted_values = sorted(values)
    index = (len(sorted_values) - 1) * pct
    lower = int(index)
    upper = min(lower + 1, len(sorted_values) - 1)
    weight = index - lower
    return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight


def summarize(samples: Iterable[Sample]) -> dict[str, object]:
    rows = list(samples)
    latencies = [row.latency_ms for row in rows]
    status_counts: dict[int, int] = {}
    for row in rows:
        status_counts[row.status_code] = status_counts.get(row.status_code, 0) + 1
    return {
        "requests": len(rows),
        "success": sum(1 for row in rows if row.ok),
        "failures": sum(1 for row in rows if not row.ok),
        "status_counts": dict(sorted(status_counts.items())),
        "p50_ms": round(percentile(latencies, 0.50), 2),
        "p95_ms": round(percentile(latencies, 0.95), 2),
        "p99_ms": round(percentile(latencies, 0.99), 2),
        "max_ms": round(max(latencies), 2) if latencies else 0.0,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Staging answer-sync load smoke helper")
    parser.add_argument("--base-url", required=True, help="Staging base URL, e.g. https://staging.example.test")
    parser.add_argument("--token", default="", help="Bearer token for a staging test user")
    parser.add_argument("--session-id", type=int, required=True, help="Staging ExamSession ID")
    parser.add_argument("--question-id", type=int, required=True, help="Question ID in the staging session exam")
    parser.add_argument("--selected-option-id", type=int, default=1, help="Option ID to submit repeatedly")
    parser.add_argument("--vus", type=int, default=100, help="Virtual users/tasks to run")
    parser.add_argument("--duration-seconds", type=int, default=60, help="Duration for autosave traffic")
    parser.add_argument("--think-ms-min", type=int, default=500, help="Minimum jitter between writes per VU")
    parser.add_argument("--think-ms-max", type=int, default=2500, help="Maximum jitter between writes per VU")
    parser.add_argument("--include-violation-burst", action="store_true", help="Send a light violation burst")
    parser.add_argument("--execute", action="store_true", help="Actually send HTTP traffic. Default is dry-run.")
    parser.add_argument("--allow-production", action="store_true", help="Allow production host traffic (requires explicit approval outside this script)")
    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> None:
    parsed = urlparse(args.base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise SystemExit("--base-url must be an absolute http(s) URL")
    host = parsed.hostname or ""
    if host in PRODUCTION_HOSTS and not args.allow_production:
        raise SystemExit("Refusing production traffic without --allow-production and explicit operator approval")
    if args.execute and not args.token:
        raise SystemExit("--token is required when --execute is used")
    if args.vus <= 0 or args.duration_seconds <= 0:
        raise SystemExit("--vus and --duration-seconds must be positive")
    if args.think_ms_max < args.think_ms_min:
        raise SystemExit("--think-ms-max must be >= --think-ms-min")


async def post_json(client: httpx.AsyncClient, endpoint: str, payload: dict[str, object]) -> Sample:
    started = time.perf_counter()
    try:
        response = await client.post(endpoint, json=payload)
        latency_ms = (time.perf_counter() - started) * 1000
        return Sample(endpoint=endpoint, status_code=response.status_code, latency_ms=latency_ms, ok=response.status_code < 500)
    except Exception:
        latency_ms = (time.perf_counter() - started) * 1000
        return Sample(endpoint=endpoint, status_code=0, latency_ms=latency_ms, ok=False)


async def answer_worker(client: httpx.AsyncClient, args: argparse.Namespace, worker_id: int, stop_at: float, samples: list[Sample]) -> None:
    endpoint = "/api/exams/submit-answer"
    sequence = 0
    while time.perf_counter() < stop_at:
        sequence += 1
        payload = {
            "session_id": args.session_id,
            "question_id": args.question_id,
            "selected_option_id": args.selected_option_id,
            "client_sequence": f"load-{worker_id}-{sequence}",
        }
        samples.append(await post_json(client, endpoint, payload))
        delay_ms = random.randint(args.think_ms_min, args.think_ms_max)
        await asyncio.sleep(delay_ms / 1000)


async def violation_burst(client: httpx.AsyncClient, args: argparse.Namespace, samples: list[Sample]) -> None:
    endpoint = "/api/exams/log-violation"
    payload = {
        "session_id": args.session_id,
        "exam_id": 0,
        "event_type": "focus_lost",
        "event_data": {"source": "load_test", "severity": "low"},
        "user_agent": "load-test-answer-sync/1.0",
        "screen_resolution": "test",
    }
    for _ in range(max(1, min(args.vus // 10, 50))):
        samples.append(await post_json(client, endpoint, payload))
        await asyncio.sleep(0.1)


async def run(args: argparse.Namespace) -> None:
    headers = {"Authorization": f"Bearer {args.token}", "Content-Type": "application/json"}
    timeout = httpx.Timeout(connect=10, read=30, write=30, pool=30)
    limits = httpx.Limits(max_connections=max(10, args.vus), max_keepalive_connections=max(10, args.vus // 2))
    samples: list[Sample] = []
    async with httpx.AsyncClient(base_url=args.base_url.rstrip("/"), headers=headers, timeout=timeout, limits=limits) as client:
        stop_at = time.perf_counter() + args.duration_seconds
        tasks = [answer_worker(client, args, index, stop_at, samples) for index in range(args.vus)]
        if args.include_violation_burst:
            tasks.append(violation_burst(client, args, samples))
        await asyncio.gather(*tasks)

    print("Answer sync load-smoke summary")
    print(summarize(samples))


def main() -> None:
    args = parse_args()
    validate_args(args)
    print("Plan:")
    print(f"  base_url={args.base_url}")
    print(f"  vus={args.vus} duration_seconds={args.duration_seconds}")
    print("  endpoint=/api/exams/submit-answer")
    if args.include_violation_burst:
        print("  endpoint=/api/exams/log-violation (light burst)")
    if not args.execute:
        print("Dry-run only. Add --execute with staging token/session/question IDs to send traffic.")
        return
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
