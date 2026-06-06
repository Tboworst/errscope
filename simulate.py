"""
Simulation script for Beacon — sends realistic error bursts from multiple
fake services so the dashboard shows grouping, counts, and sparkline activity.
"""

import json
import time
import random
import requests
from datetime import datetime, timezone

ENDPOINT = "http://localhost:7000/ingest"

# -- error scenarios -----------------------------------------------------------
# each scenario fires many times so grouping and counts are clearly visible

SCENARIOS = [
    # auth-service: null user object — numbers in message get normalized away
    # so all variations land in the same group, count climbs fast
    {
        "service": "auth-service",
        "exception_type": "AttributeError",
        "messages": [
            "NoneType object has no attribute email for user 1001",
            "NoneType object has no attribute email for user 1042",
            "NoneType object has no attribute email for user 1093",
            "NoneType object has no attribute email for user 2201",
        ],
        "stack_trace": [
            {"function": "handle_request",    "file": "/app/auth/server.py",    "line": 58},
            {"function": "authenticate_user", "file": "/app/auth/middleware.py", "line": 34},
            {"function": "find_by_token",     "file": "/app/auth/db.py",         "line": 112},
        ],
        "weight": 40,
    },
    # payment-service: missing key — request IDs vary but normalize to same fingerprint
    {
        "service": "payment-service",
        "exception_type": "KeyError",
        "messages": [
            "Missing key card_number in request 8821",
            "Missing key card_number in request 9034",
            "Missing key card_number in request 9201",
        ],
        "stack_trace": [
            {"function": "process_payment",  "file": "/app/payments/handler.py", "line": 77},
            {"function": "validate_payload", "file": "/app/payments/schema.py",  "line": 22},
        ],
        "weight": 25,
    },
    # api-gateway: db connection failing — IP varies but normalizes away
    {
        "service": "api-gateway",
        "exception_type": "ConnectionError",
        "messages": [
            "Failed to connect to database at 10.0.0.5:5432 after 3 retries",
            "Failed to connect to database at 10.0.0.5:5432 after 5 retries",
            "Failed to connect to database at 10.0.0.5:5432 after 8 retries",
        ],
        "stack_trace": [
            {"function": "get_connection", "file": "/app/gateway/pool.py",     "line": 45},
            {"function": "execute_query",  "file": "/app/gateway/db.py",       "line": 89},
            {"function": "fetch_user",     "file": "/app/gateway/queries.py",  "line": 17},
        ],
        "weight": 20,
    },
    # worker-service: bad value — job IDs vary, normalize to same group
    {
        "service": "worker-service",
        "exception_type": "ValueError",
        "messages": [
            "invalid literal for int with base 10 in job 4421",
            "invalid literal for int with base 10 in job 4489",
            "invalid literal for int with base 10 in job 5501",
        ],
        "stack_trace": [
            {"function": "process_job",   "file": "/app/worker/runner.py",  "line": 33},
            {"function": "parse_payload", "file": "/app/worker/parser.py",  "line": 61},
            {"function": "coerce_types",  "file": "/app/worker/schema.py",  "line": 88},
        ],
        "weight": 10,
    },
    # notification-service: type error
    {
        "service": "notification-service",
        "exception_type": "TypeError",
        "messages": [
            "unsupported operand for int and str in notification 771",
            "unsupported operand for int and str in notification 804",
        ],
        "stack_trace": [
            {"function": "send_notification", "file": "/app/notify/sender.py",  "line": 29},
            {"function": "build_payload",     "file": "/app/notify/builder.py", "line": 54},
        ],
        "weight": 5,
    },
    # staging: auth-service — same error class as prod but separate group in staging
    {
        "service": "auth-service",
        "environment": "staging",
        "exception_type": "AttributeError",
        "messages": [
            "NoneType object has no attribute email for user 5001",
            "NoneType object has no attribute email for user 5099",
        ],
        "stack_trace": [
            {"function": "handle_request",    "file": "/app/auth/server.py",    "line": 58},
            {"function": "authenticate_user", "file": "/app/auth/middleware.py", "line": 34},
            {"function": "find_by_token",     "file": "/app/auth/db.py",         "line": 112},
        ],
        "weight": 8,
    },
    # staging: api-gateway — new experimental endpoint throwing errors
    {
        "service": "api-gateway",
        "environment": "staging",
        "exception_type": "NotImplementedError",
        "messages": [
            "handler for route /v2/export not yet implemented",
            "handler for route /v2/export not yet implemented",
        ],
        "stack_trace": [
            {"function": "dispatch",      "file": "/app/gateway/router.py",  "line": 91},
            {"function": "route_request", "file": "/app/gateway/handler.py", "line": 14},
        ],
        "weight": 5,
    },
]

# build a weighted list so high-weight scenarios fire proportionally more
POOL = []
for scenario in SCENARIOS:
    POOL.extend([scenario] * scenario["weight"])


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def send(scenario):
    payload = {
        "timestamp": now(),
        "exception_type": scenario["exception_type"],
        "message": random.choice(scenario["messages"]),
        "stack_trace": scenario["stack_trace"],
        "service": scenario["service"],
        "environment": scenario.get("environment", "production"),
    }
    try:
        r = requests.post(ENDPOINT, json=payload, timeout=3)
        return r.status_code == 200
    except Exception:
        return False


def run():
    print(f"\nBeacon simulation — {ENDPOINT}")
    print("─" * 45)
    print("Get your dashboard open and recording ready.\n")

    # 3 second countdown — enough time to get settled before recording
    for i in range(3, 0, -1):
        print(f"  Starting in {i}...", end="\r", flush=True)
        time.sleep(1)
    print("  Firing!                    \n")

    total = 0
    failed = 0

    # ~75 second run — crosses minute boundaries so sparkline shows real data
    # total ~200 events, each group hits 50+ so Slack fires
    waves = [
        (15, 0.4,  "warming up   "),
        (40, 0.15, "ramping up   "),
        (80, 0.05, "spike!       "),
        (25, 0.4,  "settling     "),
        (40, 0.15, "steady       "),
        (25, 0.4,  "quiet        "),
        (60, 0.04, "final spike! "),
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
        time.sleep(1.5)  # visible pause between waves on the sparkline

    print(f"\n{'─' * 45}")
    print(f"Done.  {total} events sent,  {failed} failed.")
    print("Check your Slack channel and the dashboard.")


if __name__ == "__main__":
    run()
