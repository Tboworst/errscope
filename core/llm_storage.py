import hashlib
import sqlite3

from .llm_alerts import check_llm_cost_spike, check_llm_error_spike

DB_PATH = "beacon.db"

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS llm_events(
    fingerprint TEXT,
    timestamp TEXT,
    model TEXT,
    feature TEXT,
    service TEXT,
    environment TEXT,
    input_tokens INTEGER,
    output_tokens INTEGER,
    latency_ms INTEGER,
    cost_usd REAL,
    is_error INTEGER
)""")

cur.execute("""
CREATE TABLE IF NOT EXISTS llm_groups(
    fingerprint TEXT PRIMARY KEY,
    model TEXT,
    feature TEXT,
    service TEXT,
    environment TEXT,
    total_calls INTEGER,
    total_errors INTEGER,
    total_input_tokens INTEGER,
    total_output_tokens INTEGER,
    total_cost_usd REAL,
    total_latency_ms INTEGER,
    first_seen TEXT,
    last_seen TEXT
)""")

conn.commit()
conn.close()


def _llm_fingerprint(data):
    service = data.get("service") or "unknown"
    environment = data.get("environment") or "unknown"
    model = data.get("model") or "unknown"
    feature = data.get("feature") or "unknown"
    raw = f"{service}|{environment}|{model}|{feature}"
    return hashlib.md5(raw.encode()).hexdigest()


def store_llm_call(data):
    fp = _llm_fingerprint(data)
    service = data.get("service") or "unknown"
    environment = data.get("environment") or "unknown"
    model = data.get("model") or "unknown"
    feature = data.get("feature") or "unknown"
    timestamp = data.get("timestamp") or ""
    input_tokens = data.get("input_tokens") or 0
    output_tokens = data.get("output_tokens") or 0
    latency_ms = data.get("latency_ms") or 0
    cost_usd = data.get("cost_usd") or 0.0
    is_error = 1 if data.get("error") else 0

    # open a new connection per call so this is safe to call from any thread
    local_conn = sqlite3.connect(DB_PATH)
    local_cur = local_conn.cursor()

    local_cur.execute(
        "INSERT INTO llm_events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (fp, timestamp, model, feature, service, environment,
         input_tokens, output_tokens, latency_ms, cost_usd, is_error)
    )

    local_cur.execute("""
        INSERT INTO llm_groups VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(fingerprint) DO UPDATE SET
            total_calls = total_calls + 1,
            total_errors = total_errors + ?,
            total_input_tokens = total_input_tokens + ?,
            total_output_tokens = total_output_tokens + ?,
            total_cost_usd = total_cost_usd + ?,
            total_latency_ms = total_latency_ms + ?,
            last_seen = ?
    """, (
        fp, model, feature, service, environment,
        is_error, input_tokens, output_tokens, cost_usd, latency_ms, timestamp, timestamp,
        is_error, input_tokens, output_tokens, cost_usd, latency_ms, timestamp
    ))

    local_conn.commit()

    # drop raw events older than 30 days — groups are kept forever
    local_cur.execute("DELETE FROM llm_events WHERE timestamp < datetime('now', '-30 days')")
    local_conn.commit()

    local_conn.close()

    check_llm_cost_spike(fp)
    check_llm_error_spike(fp)
