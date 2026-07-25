import os
import sqlite3
import requests

# Slack webhook URL — set this env var to enable alerts
URL = os.environ.get("SLACK_WEBHOOK_URL")
DB_PATH = "beacon.db"


def check_and_alert(fingerprint, count):
    """Fire a Slack alert when a group crosses the flat count threshold."""
    threshold = 60

    if count >= threshold:
        if not URL:
            return
        message = f"[beacon] {fingerprint} has fired {count} times, reaching the threshold — check on it"
        requests.post(URL, json={"text": message})


def check_spike(fingerprint):
    """
    Spike detection: compare the last 5 minutes of events against the 5 minutes
    before that for this specific error group.

    Two cases that count as a spike:
      1. Ratio spike  — current window is 5x or more than previous window
                        e.g. 2 events before, 20 events now = 10x spike
      2. Cold spike   — previous window was 0, current window has 5+ events
                        e.g. error was silent, now suddenly firing

    We ignore anything under 3 events in the current window to avoid alerting
    on 0 → 1 or 1 → 2 noise.
    """
    try:
        conn = sqlite3.connect(DB_PATH)

        # how many times did this error fire in the last 5 minutes?
        current = conn.execute("""
            SELECT COUNT(*) FROM events
            WHERE fingerprint = ?
            AND timestamp >= datetime('now', '-5 minutes')
        """, (fingerprint,)).fetchone()[0]

        # how many times did it fire in the 5 minutes before that?
        previous = conn.execute("""
            SELECT COUNT(*) FROM events
            WHERE fingerprint = ?
            AND timestamp >= datetime('now', '-10 minutes')
            AND timestamp < datetime('now', '-5 minutes')
        """, (fingerprint,)).fetchone()[0]

        conn.close()
    except sqlite3.OperationalError:
        # DB not ready yet, skip silently
        return

    # not enough signal in the current window to be worth alerting
    if current < 3:
        return

    is_spike = False
    ratio = 0.0

    if previous == 0:
        # went from silence to 5+ events — that's a cold spike
        if current >= 5:
            is_spike = True
            ratio = float(current)  # no ratio to compute, use raw count
    else:
        ratio = current / previous
        if ratio >= 5:
            is_spike = True

    if is_spike and URL:
        message = (
            f"[beacon] spike on {fingerprint} — "
            f"{current} events in the last 5 min vs {previous} in the previous 5 min "
            f"({ratio:.1f}x)"
        )
        requests.post(URL, json={"text": message})


def check_correlated_spike(service, environment):
    """
    Fire a single combined alert when error rate AND LLM cost both spike
    for the same service in the same 5-minute window.

    This is the signal that neither Sentry nor a standalone LLM tool can
    produce — errors and AI spend moving together points to a specific class
    of failure where the AI layer is involved in the breakage.
    """
    try:
        conn = sqlite3.connect(DB_PATH)

        current_errors = conn.execute("""
            SELECT COUNT(*) FROM events
            WHERE service = ? AND environment = ?
            AND timestamp >= datetime('now', '-5 minutes')
        """, (service, environment)).fetchone()[0]

        previous_errors = conn.execute("""
            SELECT COUNT(*) FROM events
            WHERE service = ? AND environment = ?
            AND timestamp >= datetime('now', '-10 minutes')
            AND timestamp < datetime('now', '-5 minutes')
        """, (service, environment)).fetchone()[0]

        current_cost = conn.execute("""
            SELECT COALESCE(SUM(cost_usd), 0.0) FROM llm_events
            WHERE service = ? AND environment = ?
            AND timestamp >= datetime('now', '-5 minutes')
        """, (service, environment)).fetchone()[0]

        previous_cost = conn.execute("""
            SELECT COALESCE(SUM(cost_usd), 0.0) FROM llm_events
            WHERE service = ? AND environment = ?
            AND timestamp >= datetime('now', '-10 minutes')
            AND timestamp < datetime('now', '-5 minutes')
        """, (service, environment)).fetchone()[0]

        conn.close()
    except sqlite3.OperationalError:
        return

    error_spiking = current_errors >= 3 and (
        (previous_errors == 0 and current_errors >= 5) or
        (previous_errors > 0 and current_errors / previous_errors >= 5)
    )

    cost_spiking = current_cost >= 0.01 and (
        (previous_cost == 0 and current_cost >= 0.05) or
        (previous_cost > 0 and current_cost / previous_cost >= 5)
    )

    if error_spiking and cost_spiking and URL:
        message = (
            f"[beacon] correlated spike in {service}/{environment} — "
            f"{current_errors} errors and ${current_cost:.4f} LLM spend in the last 5 min "
            f"(vs {previous_errors} errors and ${previous_cost:.4f} before) — "
            f"errors and AI costs are moving together"
        )
        requests.post(URL, json={"text": message})


def alert_regression(fingerprint, exc_type, service, environment):
    """
    Fire an alert when a previously-resolved error group is seen again.

    This is the 'it came back' signal — teams care about this more than any
    other alert because it means a deploy didn't actually fix the bug.
    """
    if not URL:
        return
    message = (
        f"[beacon] regression: {exc_type} came back in {service}/{environment} "
        f"after being marked resolved — {fingerprint}"
    )
    requests.post(URL, json={"text": message})
