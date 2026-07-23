"""
Simulation script for Beacon LLM observability — sends a mix of successful and
erroring LLM call payloads to /ingest/llm for end-to-end testing.
"""

import time
import random
import requests
from datetime import datetime, timezone

ENDPOINT = "http://localhost:7000/ingest/llm"

SCENARIOS = [
    {
        "service": "search-service",
        "model": "gpt-4o",
        "feature": "semantic-search",
        "input_tokens_range": (200, 500),
        "output_tokens_range": (100, 300),
        "latency_range": (400, 900),
        "cost_per_input_token": 0.000005,
        "cost_per_output_token": 0.000015,
        "error_rate": 0.05,
        "weight": 30,
    },
    {
        "service": "document-service",
        "model": "gpt-4o",
        "feature": "document-summarizer",
        "input_tokens_range": (1000, 4000),
        "output_tokens_range": (200, 600),
        "latency_range": (800, 2000),
        "cost_per_input_token": 0.000005,
        "cost_per_output_token": 0.000015,
        "error_rate": 0.02,
        "weight": 20,
    },
    {
        "service": "chat-service",
        "model": "gpt-4o-mini",
        "feature": "chat-assistant",
        "input_tokens_range": (100, 400),
        "output_tokens_range": (50, 200),
        "latency_range": (200, 600),
        "cost_per_input_token": 0.00000015,
        "cost_per_output_token": 0.0000006,
        "error_rate": 0.01,
        "weight": 40,
    },
    {
        "service": "analytics-service",
        "model": "claude-3-5-sonnet-20241022",
        "feature": "report-generator",
        "input_tokens_range": (500, 2000),
        "output_tokens_range": (300, 800),
        "latency_range": (600, 1500),
        "cost_per_input_token": 0.000003,
        "cost_per_output_token": 0.000015,
        "error_rate": 0.08,
        "weight": 10,
    },
]

POOL = []
for scenario in SCENARIOS:
    POOL.extend([scenario] * scenario["weight"])


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def send(scenario):
    is_error = random.random() < scenario["error_rate"]
    input_tokens = 0 if is_error else random.randint(*scenario["input_tokens_range"])
    output_tokens = 0 if is_error else random.randint(*scenario["output_tokens_range"])
    latency_ms = random.randint(*scenario["latency_range"])
    cost_usd = (
        0.0 if is_error
        else input_tokens * scenario["cost_per_input_token"]
             + output_tokens * scenario["cost_per_output_token"]
    )

    payload = {
        "timestamp": now(),
        "model": scenario["model"],
        "feature": scenario["feature"],
        "service": scenario["service"],
        "environment": "production",
        "prompt_hash": str(random.randint(1_000_000, 9_999_999)),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "latency_ms": latency_ms,
        "cost_usd": cost_usd,
        "error": "LLMError: model timeout" if is_error else None,
    }
    try:
        r = requests.post(ENDPOINT, json=payload, timeout=3)
        return r.status_code == 200
    except Exception:
        return False


def run():
    print(f"\nBeacon LLM simulation — {ENDPOINT}")
    print("─" * 45)
    print("Open the dashboard and press 'l' to switch to LLM view.\n")

    for i in range(3, 0, -1):
        print(f"  Starting in {i}...", end="\r", flush=True)
        time.sleep(1)
    print("  Firing!                    \n")

    total = 0
    failed = 0

    waves = [
        (20, 0.3,  "warming up   "),
        (50, 0.1,  "ramping up   "),
        (30, 0.5,  "settling     "),
        (40, 0.1,  "steady       "),
    ]

    for count, delay, label in waves:
        print(f"  {label}  {count} events")
        for _ in range(count):
            scenario = random.choice(POOL)
            ok = send(scenario)
            total += 1
            if not ok:
                failed += 1
            time.sleep(delay)
        time.sleep(1.5)

    print(f"\n{'─' * 45}")
    print(f"Done.  {total} events sent,  {failed} failed.")
    print("Check the dashboard LLM view (press 'l').")


if __name__ == "__main__":
    run()
