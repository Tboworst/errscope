"""
Correlated simulation for Beacon — sends errors and LLM calls from the SAME
services so the correlation feature actually fires.

The existing simulate.py sends errors for auth-service, payment-service, etc.
The existing simulate_llm.py sends LLM calls for document-service, chat-service, etc.
Zero overlap, so the correlated spike alert never triggers and the modal never
shows LLM activity. This script fixes that.

Each service here makes LLM calls AND throws exceptions — which is exactly what
real AI-powered services do. A document summarizer calls GPT-4o and also crashes
when a document is malformed. A chat service calls GPT-4o-mini and also crashes
when the context window overflows.
"""

import time
import random
import requests
from datetime import datetime, timezone

ERROR_ENDPOINT = "http://localhost:7000/ingest"
LLM_ENDPOINT   = "http://localhost:7000/ingest/llm"
DEPLOY_ENDPOINT = "http://localhost:7000/deploy"


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ── Services that do both: handle requests AND make LLM calls ─────────────────

SERVICES = [
    {
        "name": "document-service",
        "environment": "production",
        "errors": [
            {
                "exception_type": "TimeoutError",
                "messages": [
                    "OpenAI request timed out after 30s for doc_id 4421",
                    "OpenAI request timed out after 30s for doc_id 5502",
                    "OpenAI request timed out after 30s for doc_id 6103",
                ],
                "stack_trace": [
                    {"function": "call_llm",    "file": "/app/document/llm.py",     "line": 61},
                    {"function": "summarize",   "file": "/app/document/handler.py", "line": 102},
                    {"function": "handle_request", "file": "/app/document/server.py", "line": 38},
                ],
                "weight": 60,
            },
            {
                "exception_type": "ValueError",
                "messages": [
                    "Document too large to process: 45231 bytes exceeds 40000 limit",
                    "Document too large to process: 51002 bytes exceeds 40000 limit",
                ],
                "stack_trace": [
                    {"function": "validate_input",    "file": "/app/document/validator.py", "line": 34},
                    {"function": "summarize_document","file": "/app/document/handler.py",   "line": 88},
                ],
                "weight": 40,
            },
        ],
        "llm": {
            "model": "gpt-4o",
            "feature": "document-summarizer",
            "input_tokens_range": (1000, 4000),
            "output_tokens_range": (200, 600),
            "latency_range": (800, 2000),
            "cost_per_input":  0.000005,
            "cost_per_output": 0.000015,
            "error_rate": 0.12,
        },
    },
    {
        "name": "chat-service",
        "environment": "production",
        "errors": [
            {
                "exception_type": "RateLimitError",
                "messages": [
                    "OpenAI rate limit hit — retry after 60s (org-xxxx)",
                    "OpenAI rate limit hit — retry after 60s (org-yyyy)",
                ],
                "stack_trace": [
                    {"function": "call_openai",  "file": "/app/chat/llm.py",     "line": 44},
                    {"function": "send_message", "file": "/app/chat/handler.py", "line": 55},
                ],
                "weight": 50,
            },
            {
                "exception_type": "ContextLengthError",
                "messages": [
                    "Context window exceeded: 16441 tokens in session abc123",
                    "Context window exceeded: 18002 tokens in session def456",
                ],
                "stack_trace": [
                    {"function": "build_context",  "file": "/app/chat/context.py",  "line": 29},
                    {"function": "send_message",   "file": "/app/chat/handler.py",  "line": 55},
                ],
                "weight": 50,
            },
        ],
        "llm": {
            "model": "gpt-4o-mini",
            "feature": "chat-assistant",
            "input_tokens_range": (100, 400),
            "output_tokens_range": (50, 200),
            "latency_range": (200, 600),
            "cost_per_input":  0.00000015,
            "cost_per_output": 0.0000006,
            "error_rate": 0.08,
        },
    },
    {
        "name": "search-service",
        "environment": "production",
        "errors": [
            {
                "exception_type": "EmbeddingError",
                "messages": [
                    "Failed to embed query: empty input after sanitization",
                    "Failed to embed query: input contains only stopwords",
                ],
                "stack_trace": [
                    {"function": "embed_query",    "file": "/app/search/embedder.py", "line": 38},
                    {"function": "semantic_search","file": "/app/search/handler.py",  "line": 71},
                ],
                "weight": 35,
            },
            {
                "exception_type": "VectorDBError",
                "messages": [
                    "Pinecone query failed: connection timeout after 10002ms",
                    "Pinecone query failed: connection timeout after 8821ms",
                ],
                "stack_trace": [
                    {"function": "query_index",    "file": "/app/search/vectordb.py", "line": 52},
                    {"function": "semantic_search","file": "/app/search/handler.py",  "line": 71},
                ],
                "weight": 65,
            },
        ],
        "llm": {
            "model": "text-embedding-3-small",
            "feature": "semantic-search",
            "input_tokens_range": (20, 100),
            "output_tokens_range": (0, 0),
            "latency_range": (80, 300),
            "cost_per_input":  0.00000002,
            "cost_per_output": 0.0,
            "error_rate": 0.15,
        },
    },
]

for s in SERVICES:
    pool = []
    for err in s["errors"]:
        pool.extend([err] * err["weight"])
    s["error_pool"] = pool


# ── Senders ───────────────────────────────────────────────────────────────────

def send_error(svc):
    err = random.choice(svc["error_pool"])
    payload = {
        "timestamp": now(),
        "exception_type": err["exception_type"],
        "message": random.choice(err["messages"]),
        "stack_trace": err["stack_trace"],
        "service": svc["name"],
        "environment": svc["environment"],
    }
    try:
        return requests.post(ERROR_ENDPOINT, json=payload, timeout=3).status_code == 200
    except Exception:
        return False


def send_llm(svc):
    llm = svc["llm"]
    is_error = random.random() < llm["error_rate"]
    input_tokens  = 0 if is_error else random.randint(*llm["input_tokens_range"])
    output_tokens = 0 if is_error else random.randint(*llm["output_tokens_range"])
    latency_ms    = random.randint(*llm["latency_range"])
    cost_usd = 0.0 if is_error else (
        input_tokens  * llm["cost_per_input"] +
        output_tokens * llm["cost_per_output"]
    )
    payload = {
        "timestamp":    now(),
        "model":        llm["model"],
        "feature":      llm["feature"],
        "service":      svc["name"],
        "environment":  svc["environment"],
        "prompt_hash":  str(random.randint(1_000_000, 9_999_999)),
        "input_tokens": input_tokens,
        "output_tokens":output_tokens,
        "latency_ms":   latency_ms,
        "cost_usd":     cost_usd,
        "error":        "LLMError: request failed" if is_error else None,
    }
    try:
        return requests.post(LLM_ENDPOINT, json=payload, timeout=3).status_code == 200
    except Exception:
        return False


def send_deploy(service, version, environment="production"):
    try:
        requests.post(DEPLOY_ENDPOINT, json={
            "timestamp":   now(),
            "service":     service,
            "version":     version,
            "environment": environment,
        }, timeout=3)
    except Exception:
        pass


# ── Simulation ────────────────────────────────────────────────────────────────

def run():
    print(f"\nBeacon correlated simulation")
    print(f"  errors  → {ERROR_ENDPOINT}")
    print(f"  llm     → {LLM_ENDPOINT}")
    print("─" * 50)
    print("  document-service  errors + gpt-4o calls")
    print("  chat-service      errors + gpt-4o-mini calls")
    print("  search-service    errors + embedding calls")
    print()

    for i in range(3, 0, -1):
        print(f"  Starting in {i}...", end="\r", flush=True)
        time.sleep(1)
    print("  Firing!                    \n")

    err_sent = 0
    llm_sent = 0
    failed   = 0

    def tick(svc):
        nonlocal err_sent, llm_sent, failed
        if send_error(svc): err_sent += 1
        else: failed += 1
        if send_llm(svc):   llm_sent += 1
        else: failed += 1

    # ── Phase 1: baseline — light traffic, build up some history
    print("  baseline        25 rounds")
    for _ in range(25):
        for svc in SERVICES:
            tick(svc)
        time.sleep(0.3)

    # ── Deploy markers — these appear in the Deploys page
    print("  deploying       document-service v1.4.0, chat-service v2.1.0")
    send_deploy("document-service", "v1.4.0")
    send_deploy("chat-service",     "v2.1.0")
    time.sleep(1.5)

    # ── Phase 2: correlated spike — errors AND LLM cost rise together
    # This is the moment that triggers check_correlated_spike() and shows
    # LLM activity in the error detail modal
    print("  spike!          80 rounds — errors and LLM cost together")
    for _ in range(80):
        for svc in SERVICES:
            tick(svc)
        time.sleep(0.05)

    time.sleep(1.5)

    # ── Phase 3: settling
    print("  settling        20 rounds")
    for _ in range(20):
        for svc in SERVICES:
            tick(svc)
        time.sleep(0.4)

    print(f"\n{'─' * 50}")
    print(f"Done.")
    print(f"  errors sent : {err_sent}")
    print(f"  llm sent    : {llm_sent}")
    print(f"  failed      : {failed}")
    print()
    print("What to look for in the dashboard:")
    print("  Issues page  — click any error → 'ai activity during spike' section")
    print("  LLM page     — cost and error rate per model/feature")
    print("  Deploys page — errors after each deploy, suspect deploy flagged")
    print("  Alerts page  — correlated spike alert if both streams moved together")
    if failed == 0:
        print("  Slack        — correlated spike alert if SLACK_WEBHOOK_URL is set")


if __name__ == "__main__":
    run()
