"""
Beacon Web API Blueprint
========================
Read + action API for the Beacon web dashboard.
All endpoints are under /api.

Design decisions documented:
- "regressed" status: storage.py already writes status='regressed' to the groups table
  when an event arrives after a group was resolved. The query simply reads that value.
- Spike heuristic: last-hour event count >= 5 AND >= 3x the average hourly rate of
  the prior 24h (consistent with the brief; alerts.py uses a 5-minute window/5x ratio
  for real-time Slack alerts — the dashboard heuristic uses a longer 1h window to show
  sustained spikes rather than momentary bursts).
- DB path: same per-call sqlite3.connect("beacon.db") pattern used by all existing modules.
"""

import os
import sqlite3
import json

from flask import Blueprint, jsonify, request, send_from_directory, abort

from . import github as gh_module

DB_PATH = "beacon.db"


def _resolve_group(fp):
    """Mark a group resolved in the current DB_PATH (testable unlike storage.resolve_group)."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "UPDATE groups SET status = 'resolved', resolved_at = datetime('now') WHERE fingerprint = ?",
        (fp,),
    )
    conn.commit()
    conn.close()

webapi = Blueprint("webapi", __name__)


# ---------------------------------------------------------------------------
# CORS helpers
# ---------------------------------------------------------------------------

_CORS_ORIGINS = {"http://localhost:5173"}


def _add_cors(response):
    # Only emit CORS headers for allowlisted cross-origin callers (the Vite dev
    # server). Same-origin requests carry no Origin header and need no CORS
    # headers; unknown origins get none, so the browser blocks them.
    origin = request.headers.get("Origin", "")
    if origin in _CORS_ORIGINS:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response


@webapi.after_request
def after_request(response):
    return _add_cors(response)


@webapi.before_request
def handle_options():
    if request.method == "OPTIONS" and request.path.startswith("/api"):
        from flask import Response
        return _add_cors(Response(status=204))


# ---------------------------------------------------------------------------
# SPA static serving helpers  (registered on app, not blueprint — see server.py)
# ---------------------------------------------------------------------------

def register_static_serving(app):
    """Register SPA fallback routes on the Flask app (not the blueprint)."""
    dist = os.path.join(os.path.dirname(__file__), "..", "web", "dist")

    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def serve_spa(path):
        if path and os.path.exists(os.path.join(dist, path)):
            return send_from_directory(dist, path)
        if os.path.exists(os.path.join(dist, "index.html")):
            return send_from_directory(dist, "index.html")
        return jsonify({"status": "beacon api running"}), 200


# ---------------------------------------------------------------------------
# Internal DB helpers
# ---------------------------------------------------------------------------

def _db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _spike_heuristic(conn, fp):
    """
    Returns True if:
      - last-hour event count >= 5
      - AND >= 3x the average hourly rate of the prior 24h
    """
    last_hour = conn.execute(
        """SELECT COUNT(*) FROM events
           WHERE fingerprint = ? AND timestamp >= datetime('now', '-1 hour')""",
        (fp,),
    ).fetchone()[0]

    if last_hour < 5:
        return False

    prior_24h = conn.execute(
        """SELECT COUNT(*) FROM events
           WHERE fingerprint = ?
             AND timestamp >= datetime('now', '-25 hours')
             AND timestamp < datetime('now', '-1 hour')""",
        (fp,),
    ).fetchone()[0]

    avg_hourly_prior = prior_24h / 24.0
    if avg_hourly_prior == 0:
        return True  # cold spike — was silent, now firing
    return last_hour >= 3 * avg_hourly_prior


def _trend_buckets(conn, fp):
    """16 hourly event-count buckets ending now (oldest first)."""
    rows = conn.execute(
        """SELECT
               CAST((julianday('now') - julianday(timestamp)) * 24 AS INTEGER) AS hours_ago,
               COUNT(*) AS cnt
           FROM events
           WHERE fingerprint = ?
             AND timestamp >= datetime('now', '-16 hours')
           GROUP BY hours_ago""",
        (fp,),
    ).fetchall()

    buckets = [0] * 16
    for row in rows:
        idx = 15 - min(int(row["hours_ago"]), 15)
        buckets[idx] += row["cnt"]
    return buckets


def _parse_chain(chain_str):
    """Convert 'a->b->c' stored string into list ['a','b','c']."""
    if not chain_str:
        return []
    return chain_str.split("->")


def _group_to_issue(row, spiking, trend):
    github = None
    if row["github_issue_url"]:
        github = {"n": row["github_issue_number"], "url": row["github_issue_url"]}
    return {
        "fp": row["fingerprint"],
        "exc": row["exception_type"],
        "msg": row["normalize_message"],
        "chain": _parse_chain(row["function_chain"]),
        "count": row["count"],
        "first_seen": row["first_seen"],
        "last_seen": row["last_seen"],
        "service": row["service"],
        "env": row["environment"],
        "status": row["status"] or "active",
        "spiking": spiking,
        "trend": trend,
        "github": github,
    }


# ---------------------------------------------------------------------------
# GET /api/issues
# ---------------------------------------------------------------------------

@webapi.route("/api/issues")
def get_issues():
    env = request.args.get("env")
    q = request.args.get("q", "").strip().lower()

    sql = "SELECT * FROM groups WHERE 1=1"
    params = []
    if env:
        sql += " AND environment = ?"
        params.append(env)
    sql += " ORDER BY count DESC"

    conn = _db()
    rows = conn.execute(sql, params).fetchall()

    issues = []
    for row in rows:
        if q and not any(
            q in (row["exception_type"] or "").lower()
            or q in (row["normalize_message"] or "").lower()
            or q in (row["service"] or "").lower()
            for _ in [1]
        ):
            continue
        spiking = _spike_heuristic(conn, row["fingerprint"])
        trend = _trend_buckets(conn, row["fingerprint"])
        issues.append(_group_to_issue(row, spiking, trend))

    conn.close()
    return jsonify({"issues": issues})


# ---------------------------------------------------------------------------
# GET /api/issues/<fp>
# ---------------------------------------------------------------------------

@webapi.route("/api/issues/<fp>")
def get_issue(fp):
    conn = _db()
    row = conn.execute("SELECT * FROM groups WHERE fingerprint = ?", (fp,)).fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "not found"}), 404

    spiking = _spike_heuristic(conn, fp)
    trend = _trend_buckets(conn, fp)
    issue = _group_to_issue(row, spiking, trend)

    # LLM activity for same service+env in the last hour
    service = row["service"]
    environment = row["environment"]
    llm_row = conn.execute(
        """SELECT COUNT(*) as calls,
                  COALESCE(SUM(cost_usd), 0.0) as cost_usd,
                  SUM(is_error) as errors
           FROM llm_events
           WHERE service = ? AND environment = ?
             AND timestamp >= datetime('now', '-1 hour')""",
        (service, environment),
    ).fetchone()

    if llm_row and llm_row["calls"] > 0:
        issue["llm"] = {
            "calls": llm_row["calls"],
            "cost_usd": round(llm_row["cost_usd"], 4),
            "errors": llm_row["errors"] or 0,
        }
    else:
        issue["llm"] = None

    conn.close()
    return jsonify(issue)


# ---------------------------------------------------------------------------
# POST /api/issues/<fp>/resolve
# ---------------------------------------------------------------------------

@webapi.route("/api/issues/<fp>/resolve", methods=["POST"])
def resolve_issue(fp):
    conn = _db()
    row = conn.execute("SELECT * FROM groups WHERE fingerprint = ?", (fp,)).fetchone()
    conn.close()
    if not row:
        return jsonify({"error": "not found"}), 404

    _resolve_group(fp)

    # Close linked GitHub issue if configured
    github_closed = False
    issue_number = row["github_issue_number"]
    if issue_number and gh_module.github_configured():
        try:
            gh_module.close_issue(issue_number)
            github_closed = True
        except Exception:
            pass

    return jsonify({"ok": True, "status": "resolved", "github_closed": github_closed})


# ---------------------------------------------------------------------------
# POST /api/issues/<fp>/reopen
# ---------------------------------------------------------------------------

@webapi.route("/api/issues/<fp>/reopen", methods=["POST"])
def reopen_issue(fp):
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT fingerprint FROM groups WHERE fingerprint = ?", (fp,)
    ).fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "not found"}), 404

    conn.execute(
        "UPDATE groups SET status = 'active', resolved_at = NULL WHERE fingerprint = ?",
        (fp,),
    )
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "status": "active"})


# ---------------------------------------------------------------------------
# POST /api/issues/<fp>/github
# ---------------------------------------------------------------------------

@webapi.route("/api/issues/<fp>/github", methods=["POST"])
def create_github_issue(fp):
    if not gh_module.github_configured():
        return jsonify({"ok": False, "error": "github_not_configured"}), 400

    conn = _db()
    row = conn.execute("SELECT * FROM groups WHERE fingerprint = ?", (fp,)).fetchone()
    conn.close()
    if not row:
        return jsonify({"error": "not found"}), 404

    try:
        number, url = gh_module.create_issue(
            fp=fp,
            exc_type=row["exception_type"],
            norm_msg=row["normalize_message"],
            fn_chain=row["function_chain"],
            count=row["count"],
            first_seen=row["first_seen"],
            last_seen=row["last_seen"],
            service=row["service"],
            environment=row["environment"],
        )
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

    # Persist issue reference on the group
    local_conn = sqlite3.connect(DB_PATH)
    local_conn.execute(
        "UPDATE groups SET github_issue_url = ?, github_issue_number = ? WHERE fingerprint = ?",
        (url, number, fp),
    )
    local_conn.commit()
    local_conn.close()

    return jsonify({"ok": True, "github": {"n": number, "url": url}})


# ---------------------------------------------------------------------------
# GET /api/overview
# ---------------------------------------------------------------------------

@webapi.route("/api/overview")
def get_overview():
    env = request.args.get("env")
    conn = _db()

    env_filter = "AND environment = ?" if env else ""
    env_params = [env] if env else []

    total_events = conn.execute(
        f"SELECT COUNT(*) FROM events WHERE 1=1 {env_filter}",
        env_params,
    ).fetchone()[0]

    active_issues = conn.execute(
        f"SELECT COUNT(*) FROM groups WHERE status = 'active' {env_filter}",
        env_params,
    ).fetchone()[0]

    resolved_30d = conn.execute(
        f"""SELECT COUNT(*) FROM groups
            WHERE status = 'resolved'
              AND resolved_at >= datetime('now', '-30 days')
              {env_filter}""",
        env_params,
    ).fetchone()[0]

    # Events per minute in the last 5 minutes
    recent_5min = conn.execute(
        f"""SELECT COUNT(*) FROM events
            WHERE timestamp >= datetime('now', '-5 minutes') {env_filter}""",
        env_params,
    ).fetchone()[0]
    events_per_min = round(recent_5min / 5.0, 1)

    # 20 per-minute buckets for the last 20 minutes
    spark_rows = conn.execute(
        f"""SELECT
               CAST((julianday('now') - julianday(timestamp)) * 1440 AS INTEGER) AS mins_ago,
               COUNT(*) as cnt
            FROM events
            WHERE timestamp >= datetime('now', '-20 minutes') {env_filter}
            GROUP BY mins_ago""",
        env_params,
    ).fetchall()
    events_spark = [0] * 20
    for r in spark_rows:
        idx = 19 - min(int(r["mins_ago"]), 19)
        events_spark[idx] += r["cnt"]

    # 14 daily event counts
    daily_rows = conn.execute(
        f"""SELECT
               CAST(julianday('now') - julianday(timestamp) AS INTEGER) AS days_ago,
               COUNT(*) as cnt
            FROM events
            WHERE timestamp >= datetime('now', '-14 days') {env_filter}
            GROUP BY days_ago""",
        env_params,
    ).fetchall()
    events_daily = [0] * 14
    for r in daily_rows:
        idx = 13 - min(int(r["days_ago"]), 13)
        events_daily[idx] += r["cnt"]

    # 14 daily new-group counts (first_seen falls in each day)
    new_group_rows = conn.execute(
        f"""SELECT
               CAST(julianday('now') - julianday(first_seen) AS INTEGER) AS days_ago,
               COUNT(*) as cnt
            FROM groups
            WHERE first_seen >= datetime('now', '-14 days') {env_filter}
            GROUP BY days_ago""",
        env_params,
    ).fetchall()
    active_daily = [0] * 14
    for r in new_group_rows:
        idx = 13 - min(int(r["days_ago"]), 13)
        active_daily[idx] += r["cnt"]

    # 14 daily resolved counts (resolved_at falls in each day)
    resolved_rows = conn.execute(
        f"""SELECT
               CAST(julianday('now') - julianday(resolved_at) AS INTEGER) AS days_ago,
               COUNT(*) as cnt
            FROM groups
            WHERE resolved_at IS NOT NULL
              AND resolved_at >= datetime('now', '-14 days') {env_filter}
            GROUP BY days_ago""",
        env_params,
    ).fetchall()
    resolved_daily = [0] * 14
    for r in resolved_rows:
        idx = 13 - min(int(r["days_ago"]), 13)
        resolved_daily[idx] += r["cnt"]

    # Spiking and regressed counts
    all_groups = conn.execute(
        f"SELECT fingerprint, status FROM groups WHERE 1=1 {env_filter}",
        env_params,
    ).fetchall()

    spiking_count = 0
    regressed_count = 0
    for grp in all_groups:
        if _spike_heuristic(conn, grp["fingerprint"]):
            spiking_count += 1
        if grp["status"] == "regressed":
            regressed_count += 1

    conn.close()
    return jsonify({
        "total_events": total_events,
        "active_issues": active_issues,
        "resolved_30d": resolved_30d,
        "events_per_min": events_per_min,
        "events_spark": events_spark,
        "events_daily": events_daily,
        "active_daily": active_daily,
        "resolved_daily": resolved_daily,
        "spiking_count": spiking_count,
        "regressed_count": regressed_count,
    })


# ---------------------------------------------------------------------------
# GET /api/llm
# ---------------------------------------------------------------------------

@webapi.route("/api/llm")
def get_llm():
    env = request.args.get("env")
    conn = _db()

    env_clause = "AND environment = ?" if env else ""
    env_params = [env] if env else []

    group_rows = conn.execute(
        f"""SELECT model, feature, service, environment,
                   total_calls, total_errors, total_input_tokens, total_output_tokens,
                   total_cost_usd, total_latency_ms, last_seen
            FROM llm_groups
            WHERE 1=1 {env_clause}
            ORDER BY total_cost_usd DESC""",
        env_params,
    ).fetchall()

    groups = []
    for r in group_rows:
        calls = r["total_calls"] or 0
        errors = r["total_errors"] or 0
        err_pct = round(errors / calls * 100, 1) if calls > 0 else 0.0
        avg_latency = round(r["total_latency_ms"] / calls) if calls > 0 else 0
        groups.append({
            "model": r["model"],
            "feature": r["feature"],
            "service": r["service"],
            "env": r["environment"],
            "calls": calls,
            "errors": errors,
            "err_pct": err_pct,
            "avg_latency_ms": avg_latency,
            "cost_usd": round(r["total_cost_usd"] or 0.0, 4),
            "last_seen": r["last_seen"],
            "tokens_in": r["total_input_tokens"] or 0,
            "tokens_out": r["total_output_tokens"] or 0,
        })

    totals_row = conn.execute(
        f"""SELECT SUM(total_calls) as calls, SUM(total_cost_usd) as cost_usd,
                   SUM(total_errors) as errors, SUM(total_latency_ms) as total_latency_ms,
                   SUM(total_calls) as total_calls_sum
            FROM llm_groups WHERE 1=1 {env_clause}""",
        env_params,
    ).fetchone()
    total_calls = totals_row["calls"] or 0
    total_cost = round(totals_row["cost_usd"] or 0.0, 4)
    total_errors = totals_row["errors"] or 0
    total_latency = totals_row["total_latency_ms"] or 0
    avg_latency_ms = round(total_latency / total_calls) if total_calls > 0 else 0

    # 14-day daily aggregates from llm_events
    def _daily_series(col_expr, where_extra=""):
        rows = conn.execute(
            f"""SELECT
                    CAST(julianday('now') - julianday(timestamp) AS INTEGER) AS days_ago,
                    {col_expr} as val
                FROM llm_events
                WHERE timestamp >= datetime('now', '-14 days')
                  {env_clause} {where_extra}
                GROUP BY days_ago""",
            env_params,
        ).fetchall()
        buckets = [0] * 14
        for r in rows:
            idx = 13 - min(int(r["days_ago"]), 13)
            buckets[idx] += r["val"] or 0
        return buckets

    calls_daily = _daily_series("COUNT(*)")
    cost_daily_rows = conn.execute(
        f"""SELECT
                CAST(julianday('now') - julianday(timestamp) AS INTEGER) AS days_ago,
                COALESCE(SUM(cost_usd), 0.0) as val
            FROM llm_events
            WHERE timestamp >= datetime('now', '-14 days')
              {env_clause}
            GROUP BY days_ago""",
        env_params,
    ).fetchall()
    cost_daily = [0.0] * 14
    for r in cost_daily_rows:
        idx = 13 - min(int(r["days_ago"]), 13)
        cost_daily[idx] = round((cost_daily[idx] or 0) + (r["val"] or 0), 4)

    errors_daily = _daily_series("SUM(is_error)")
    latency_daily_rows = conn.execute(
        f"""SELECT
                CAST(julianday('now') - julianday(timestamp) AS INTEGER) AS days_ago,
                CASE WHEN COUNT(*) > 0 THEN SUM(latency_ms) / COUNT(*) ELSE 0 END as val
            FROM llm_events
            WHERE timestamp >= datetime('now', '-14 days')
              {env_clause}
            GROUP BY days_ago""",
        env_params,
    ).fetchall()
    latency_daily = [0] * 14
    for r in latency_daily_rows:
        idx = 13 - min(int(r["days_ago"]), 13)
        latency_daily[idx] = int(r["val"] or 0)

    conn.close()
    return jsonify({
        "groups": groups,
        "totals": {
            "calls": total_calls,
            "cost_usd": total_cost,
            "errors": total_errors,
            "avg_latency_ms": avg_latency_ms,
        },
        "calls_daily": calls_daily,
        "cost_daily": cost_daily,
        "errors_daily": errors_daily,
        "latency_daily": latency_daily,
    })


# ---------------------------------------------------------------------------
# GET /api/deploys
# ---------------------------------------------------------------------------

@webapi.route("/api/deploys")
def get_deploys():
    env = request.args.get("env")
    conn = _db()

    env_clause = "AND environment = ?" if env else ""
    env_params = [env] if env else []

    deploy_rows = conn.execute(
        f"""SELECT id, service, environment, version, timestamp
            FROM deploys WHERE 1=1 {env_clause}
            ORDER BY timestamp DESC""",
        env_params,
    ).fetchall()

    # For each deploy, compute errors_after = events for that service+env
    # from deploy time until the next deploy of same service+env (or now).
    deploys = []
    for i, d in enumerate(deploy_rows):
        service = d["service"]
        environment = d["environment"]
        deploy_ts = d["timestamp"]

        # find next deploy of same service+env (looking earlier in the list since ordered DESC)
        next_ts = None
        for j in range(i):
            prev = deploy_rows[j]
            if prev["service"] == service and prev["environment"] == environment:
                next_ts = prev["timestamp"]
                break

        if next_ts:
            errors_after = conn.execute(
                """SELECT COUNT(*) FROM events
                   WHERE service = ? AND environment = ?
                     AND timestamp >= ? AND timestamp < ?""",
                (service, environment, deploy_ts, next_ts),
            ).fetchone()[0]
        else:
            errors_after = conn.execute(
                """SELECT COUNT(*) FROM events
                   WHERE service = ? AND environment = ?
                     AND timestamp >= ?""",
                (service, environment, deploy_ts),
            ).fetchone()[0]

        # suspect: errors_after >= 20 AND deploy within last 24h
        suspect = (errors_after >= 20) and (
            conn.execute(
                "SELECT COUNT(*) FROM deploys WHERE id = ? AND timestamp >= datetime('now', '-24 hours')",
                (d["id"],),
            ).fetchone()[0]
            > 0
        )

        # top error group fingerprint for suspect — bounded to this deploy's
        # window (until the next deploy of the same service+env, if any)
        suspect_fp = None
        if suspect:
            if next_ts:
                top = conn.execute(
                    """SELECT fingerprint, COUNT(*) as cnt FROM events
                       WHERE service = ? AND environment = ?
                         AND timestamp >= ? AND timestamp < ?
                       GROUP BY fingerprint ORDER BY cnt DESC LIMIT 1""",
                    (service, environment, deploy_ts, next_ts),
                ).fetchone()
            else:
                top = conn.execute(
                    """SELECT fingerprint, COUNT(*) as cnt FROM events
                       WHERE service = ? AND environment = ? AND timestamp >= ?
                       GROUP BY fingerprint ORDER BY cnt DESC LIMIT 1""",
                    (service, environment, deploy_ts),
                ).fetchone()
            if top:
                suspect_fp = top["fingerprint"]

        deploys.append({
            "version": d["version"],
            "service": service,
            "env": environment,
            "deployed_at": deploy_ts,
            "errors_after": errors_after,
            "suspect": suspect,
            "suspect_fp": suspect_fp,
        })

    # Stats
    deploys_7d = conn.execute(
        f"""SELECT COUNT(*) FROM deploys
            WHERE timestamp >= datetime('now', '-7 days') {env_clause}""",
        env_params,
    ).fetchone()[0]

    services_count = conn.execute(
        f"SELECT COUNT(DISTINCT service) FROM deploys WHERE 1=1 {env_clause}",
        env_params,
    ).fetchone()[0]

    last_deploy_row = conn.execute(
        f"""SELECT timestamp, service, environment FROM deploys
            WHERE 1=1 {env_clause}
            ORDER BY timestamp DESC LIMIT 1""",
        env_params,
    ).fetchone()

    errors_after_last = 0
    last_deploy_at = None
    if last_deploy_row:
        last_deploy_at = last_deploy_row["timestamp"]
        errors_after_last = conn.execute(
            """SELECT COUNT(*) FROM events
               WHERE service = ? AND environment = ? AND timestamp >= ?""",
            (last_deploy_row["service"], last_deploy_row["environment"], last_deploy_row["timestamp"]),
        ).fetchone()[0]

    conn.close()
    return jsonify({
        "deploys": deploys,
        "stats": {
            "deploys_7d": deploys_7d,
            "services": services_count,
            "errors_after_last": errors_after_last,
            "last_deploy_at": last_deploy_at,
        },
    })


# ---------------------------------------------------------------------------
# GET /api/alerts
# ---------------------------------------------------------------------------

_ALERT_RULES = [
    {"name": "Count threshold", "rule": "group count >= 60 events"},
    {"name": "Error rate spike", "rule": "3× baseline in last hour"},
    {"name": "Regression", "rule": "resolved group re-fires"},
    {"name": "Suspect deploy", "rule": "20+ errors within 24h of deploy"},
    {"name": "LLM error rate", "rule": "LLM error rate >= 10%"},
    {"name": "LLM cost spike", "rule": "LLM cost 5× baseline in 5 min"},
    {"name": "Correlated spike", "rule": "errors and LLM cost spike together"},
]


@webapi.route("/api/alerts")
def get_alerts():
    env = request.args.get("env")
    conn = _db()

    env_clause = "AND environment = ?" if env else ""
    env_params = [env] if env else []

    alerts = []

    # --- spike alerts ---
    group_rows = conn.execute(
        f"SELECT * FROM groups WHERE 1=1 {env_clause}",
        env_params,
    ).fetchall()

    for row in group_rows:
        fp = row["fingerprint"]
        if _spike_heuristic(conn, fp):
            last_hour = conn.execute(
                "SELECT COUNT(*) FROM events WHERE fingerprint = ? AND timestamp >= datetime('now', '-1 hour')",
                (fp,),
            ).fetchone()[0]
            prior_24h = conn.execute(
                """SELECT COUNT(*) FROM events WHERE fingerprint = ?
                   AND timestamp >= datetime('now', '-25 hours')
                   AND timestamp < datetime('now', '-1 hour')""",
                (fp,),
            ).fetchone()[0]
            avg_prior = prior_24h / 24.0
            ratio = round(last_hour / avg_prior, 1) if avg_prior > 0 else float(last_hour)
            alerts.append({
                "id": f"spike:{fp}",
                "sev": "spike",
                "title": f"{row['exception_type']} spiking in {row['service']}",
                "detail": f"{last_hour} events · {ratio}× over baseline",
                "service": row["service"],
                "env": row["environment"],
                "ts": row["last_seen"],
                "link": {"type": "issue", "fp": fp},
            })

    # --- regression alerts ---
    regressed_rows = conn.execute(
        f"SELECT * FROM groups WHERE status = 'regressed' {env_clause}",
        env_params,
    ).fetchall()
    for row in regressed_rows:
        alerts.append({
            "id": f"regression:{row['fingerprint']}",
            "sev": "regression",
            "title": f"{row['exception_type']} regressed in {row['service']}",
            "detail": f"{row['count']} events · previously resolved",
            "service": row["service"],
            "env": row["environment"],
            "ts": row["last_seen"],
            "link": {"type": "issue", "fp": row["fingerprint"]},
        })

    # --- threshold alerts ---
    threshold_rows = conn.execute(
        f"SELECT * FROM groups WHERE count >= 60 {env_clause}",
        env_params,
    ).fetchall()
    for row in threshold_rows:
        alerts.append({
            "id": f"threshold:{row['fingerprint']}",
            "sev": "threshold",
            "title": f"{row['exception_type']} crossed threshold in {row['service']}",
            "detail": f"{row['count']} events · >= 60 threshold",
            "service": row["service"],
            "env": row["environment"],
            "ts": row["last_seen"],
            "link": {"type": "issue", "fp": row["fingerprint"]},
        })

    # --- deploy suspect alerts ---
    deploy_rows = conn.execute(
        f"""SELECT * FROM deploys
            WHERE timestamp >= datetime('now', '-24 hours') {env_clause}
            ORDER BY timestamp DESC""",
        env_params,
    ).fetchall()
    for d in deploy_rows:
        # bound this deploy's window at the next deploy of the same service+env
        next_row = conn.execute(
            """SELECT timestamp FROM deploys
               WHERE service = ? AND environment = ? AND timestamp > ?
               ORDER BY timestamp ASC LIMIT 1""",
            (d["service"], d["environment"], d["timestamp"]),
        ).fetchone()
        next_ts = next_row["timestamp"] if next_row else None

        if next_ts:
            errors_after = conn.execute(
                """SELECT COUNT(*) FROM events
                   WHERE service = ? AND environment = ?
                     AND timestamp >= ? AND timestamp < ?""",
                (d["service"], d["environment"], d["timestamp"], next_ts),
            ).fetchone()[0]
        else:
            errors_after = conn.execute(
                """SELECT COUNT(*) FROM events
                   WHERE service = ? AND environment = ? AND timestamp >= ?""",
                (d["service"], d["environment"], d["timestamp"]),
            ).fetchone()[0]
        if errors_after >= 20:
            if next_ts:
                top = conn.execute(
                    """SELECT fingerprint, COUNT(*) as cnt FROM events
                       WHERE service = ? AND environment = ?
                         AND timestamp >= ? AND timestamp < ?
                       GROUP BY fingerprint ORDER BY cnt DESC LIMIT 1""",
                    (d["service"], d["environment"], d["timestamp"], next_ts),
                ).fetchone()
            else:
                top = conn.execute(
                    """SELECT fingerprint, COUNT(*) as cnt FROM events
                       WHERE service = ? AND environment = ? AND timestamp >= ?
                       GROUP BY fingerprint ORDER BY cnt DESC LIMIT 1""",
                    (d["service"], d["environment"], d["timestamp"]),
                ).fetchone()
            suspect_fp = top["fingerprint"] if top else None
            alerts.append({
                "id": f"deploy:{d['id']}",
                "sev": "deploy",
                "title": f"Suspect deploy {d['version']} in {d['service']}",
                "detail": f"{errors_after} errors after deploy",
                "service": d["service"],
                "env": d["environment"],
                "ts": d["timestamp"],
                "link": {"type": "page", "page": "deploys"},
            })

    # --- LLM alerts ---
    llm_group_rows = conn.execute(
        f"""SELECT * FROM llm_groups WHERE 1=1 {env_clause}""",
        env_params,
    ).fetchall()
    for row in llm_group_rows:
        calls = row["total_calls"] or 0
        errors = row["total_errors"] or 0
        err_pct = (errors / calls * 100) if calls > 0 else 0.0
        if err_pct >= 10:
            alerts.append({
                "id": f"llm:err:{row['fingerprint']}",
                "sev": "llm",
                "title": f"LLM error rate high: {row['feature']} ({row['model']})",
                "detail": f"{err_pct:.1f}% error rate · {errors}/{calls} calls",
                "service": row["service"],
                "env": row["environment"],
                "ts": row["last_seen"],
                "link": {"type": "page", "page": "llm"},
            })

    # LLM cost spike: compare last 5 min vs prior 5 min per group
    llm_cost_spike_rows = conn.execute(
        f"""SELECT fingerprint, model, feature, service, environment,
                   SUM(CASE WHEN timestamp >= datetime('now', '-5 minutes') THEN cost_usd ELSE 0 END) as cur,
                   SUM(CASE WHEN timestamp >= datetime('now', '-10 minutes')
                               AND timestamp < datetime('now', '-5 minutes') THEN cost_usd ELSE 0 END) as prev
            FROM llm_events
            WHERE timestamp >= datetime('now', '-10 minutes')
              {env_clause}
            GROUP BY fingerprint""",
        env_params,
    ).fetchall()
    for row in llm_cost_spike_rows:
        cur = row["cur"] or 0.0
        prev = row["prev"] or 0.0
        if cur >= 0.01 and (
            (prev == 0 and cur >= 0.05) or (prev > 0 and cur / prev >= 5)
        ):
            ratio = round(cur / prev, 1) if prev > 0 else float(cur)
            alerts.append({
                "id": f"llm:cost:{row['fingerprint']}",
                "sev": "llm",
                "title": f"LLM cost spike: {row['feature']} ({row['model']})",
                "detail": f"${cur:.4f} in last 5 min · {ratio}× baseline",
                "service": row["service"],
                "env": row["environment"],
                "ts": None,
                "link": {"type": "page", "page": "llm"},
            })

    conn.close()

    # Sort by ts desc (None last)
    alerts.sort(key=lambda a: a.get("ts") or "", reverse=True)

    slack_connected = bool(os.environ.get("SLACK_WEBHOOK_URL"))

    return jsonify({
        "alerts": alerts,
        "rules": _ALERT_RULES,
        "slack_connected": slack_connected,
    })


# ---------------------------------------------------------------------------
# GET /api/meta
# ---------------------------------------------------------------------------

@webapi.route("/api/meta")
def get_meta():
    conn = _db()

    service_rows = conn.execute(
        """SELECT service, COUNT(*) as cnt FROM events
           GROUP BY service ORDER BY cnt DESC"""
    ).fetchall()
    services = [{"name": r["service"], "count": r["cnt"]} for r in service_rows]

    env_rows = conn.execute(
        """SELECT environment, COUNT(*) as cnt FROM groups
           WHERE status = 'active'
           GROUP BY environment ORDER BY cnt DESC"""
    ).fetchall()
    envs = [{"name": r["environment"], "count": r["cnt"]} for r in env_rows]

    event_count = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    conn.close()

    db_bytes = 0
    try:
        db_bytes = os.path.getsize(DB_PATH)
    except OSError:
        pass

    return jsonify({
        "services": services,
        "envs": envs,
        "health": {
            "ok": True,
            "db_bytes": db_bytes,
            "event_count": event_count,
            "retention_days": 30,
            "host": "localhost:7000",
            "api_key_set": bool(os.environ.get("BEACON_API_KEY")),
        },
        "github_configured": gh_module.github_configured(),
        "slack_connected": bool(os.environ.get("SLACK_WEBHOOK_URL")),
    })
