import os
import sqlite3
import requests

URL = os.environ.get("SLACK_WEBHOOK_URL")
DB_PATH = "beacon.db"


def check_llm_cost_spike(fingerprint):
    """
    Spike detection for LLM cost: compare SUM(cost_usd) in the last 5 minutes
    against the prior 5-minute window.

    Two cases that count as a spike:
      1. Ratio spike  — current window is 5x or more than previous window
      2. Cold spike   — previous=$0 and current >= $0.05

    Noise floor: current window must have >= $0.01 spend to be worth alerting.
    """
    try:
        conn = sqlite3.connect(DB_PATH)

        current = conn.execute("""
            SELECT COALESCE(SUM(cost_usd), 0.0) FROM llm_events
            WHERE fingerprint = ?
            AND timestamp >= datetime('now', '-5 minutes')
        """, (fingerprint,)).fetchone()[0]

        previous = conn.execute("""
            SELECT COALESCE(SUM(cost_usd), 0.0) FROM llm_events
            WHERE fingerprint = ?
            AND timestamp >= datetime('now', '-10 minutes')
            AND timestamp < datetime('now', '-5 minutes')
        """, (fingerprint,)).fetchone()[0]

        conn.close()
    except sqlite3.OperationalError:
        return

    if current < 0.01:
        return

    is_spike = False
    ratio = 0.0

    if previous == 0:
        if current >= 0.05:
            is_spike = True
            ratio = float(current)
    else:
        ratio = current / previous
        if ratio >= 5:
            is_spike = True

    if is_spike and URL:
        message = (
            f"[beacon] LLM cost spike on {fingerprint} — "
            f"${current:.4f} in the last 5 min vs ${previous:.4f} in the previous 5 min "
            f"({ratio:.1f}x)"
        )
        requests.post(URL, json={"text": message})


def check_llm_error_spike(fingerprint):
    """
    Spike detection for LLM errors: compare error counts in the last 5 minutes
    against the prior 5-minute window.

    Identical thresholds to check_spike() in alerts.py:
      1. Ratio spike  — current window is 5x or more than previous window
      2. Cold spike   — previous=0 and current >= 5
    Minimum 3 errors in the current window to avoid noise.
    """
    try:
        conn = sqlite3.connect(DB_PATH)

        current = conn.execute("""
            SELECT COUNT(*) FROM llm_events
            WHERE fingerprint = ?
            AND is_error = 1
            AND timestamp >= datetime('now', '-5 minutes')
        """, (fingerprint,)).fetchone()[0]

        previous = conn.execute("""
            SELECT COUNT(*) FROM llm_events
            WHERE fingerprint = ?
            AND is_error = 1
            AND timestamp >= datetime('now', '-10 minutes')
            AND timestamp < datetime('now', '-5 minutes')
        """, (fingerprint,)).fetchone()[0]

        conn.close()
    except sqlite3.OperationalError:
        return

    if current < 3:
        return

    is_spike = False
    ratio = 0.0

    if previous == 0:
        if current >= 5:
            is_spike = True
            ratio = float(current)
    else:
        ratio = current / previous
        if ratio >= 5:
            is_spike = True

    if is_spike and URL:
        message = (
            f"[beacon] LLM error spike on {fingerprint} — "
            f"{current} errors in the last 5 min vs {previous} in the previous 5 min "
            f"({ratio:.1f}x)"
        )
        requests.post(URL, json={"text": message})
