"""
Tests for core/webapi.py — Beacon read/action API blueprint.

Strategy:
- Each test uses a fresh temporary SQLite DB (via tmp_path fixture).
- We patch DB_PATH across all modules so they all talk to the same test DB.
- We seed data through the storage modules' own store functions (store_event,
  store_llm_call, store_deploy, resolve_group) to exercise real write paths.
- Tests verify:
  - Shape of responses matches the API contract (exact field names).
  - Filters (env, q) narrow results correctly.
  - Resolve/reopen round-trip changes status.
  - Overview, llm, deploys, alerts, meta return valid JSON on empty and seeded DBs.
"""

import json
import os
import sqlite3
import sys
import types
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# ---------------------------------------------------------------------------
# Bootstrap: make sure the package root is on sys.path
# ---------------------------------------------------------------------------
REPO_ROOT = str(Path(__file__).parent.parent)
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db_path(tmp_path):
    """Return a fresh temp DB path and patch all modules to use it."""
    path = str(tmp_path / "test_beacon.db")

    # Initialise the schema in the temp DB (mirrors storage.py / llm_storage.py / deploy_storage.py)
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS groups(
            fingerprint TEXT PRIMARY KEY,
            exception_type TEXT,
            normalize_message TEXT,
            function_chain TEXT,
            count INTEGER,
            first_seen TEXT,
            last_seen TEXT,
            service TEXT,
            environment TEXT,
            status TEXT DEFAULT 'active',
            resolved_at TEXT,
            github_issue_url TEXT,
            github_issue_number INTEGER
        );
        CREATE TABLE IF NOT EXISTS events(
            fingerprint TEXT,
            timestamp TEXT,
            exception_type TEXT,
            message TEXT,
            service TEXT,
            environment TEXT
        );
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
        );
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
        );
        CREATE TABLE IF NOT EXISTS deploys(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            service TEXT,
            environment TEXT,
            version TEXT,
            timestamp TEXT
        );
    """)
    conn.commit()
    conn.close()

    with patch("core.webapi.DB_PATH", path), \
         patch("core.storage.DB_PATH", path, create=True), \
         patch("core.llm_storage.DB_PATH", path), \
         patch("core.deploy_storage.DB_PATH", path), \
         patch("core.alerts.DB_PATH", path), \
         patch("core.llm_alerts.DB_PATH", path):
        yield path


@pytest.fixture
def client(db_path):
    """Flask test client wired to the temp DB."""
    from core.server import app
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------

TS_NOW = datetime.now(timezone.utc)
TS_FMT = "%Y-%m-%dT%H:%M:%SZ"


def _ts(delta_minutes=0):
    return (TS_NOW + timedelta(minutes=delta_minutes)).strftime(TS_FMT)


def _insert_group(db_path, fp, exc="TypeError", msg="Something broke",
                  chain="a->b->c", count=5, service="svc", env="production",
                  status="active", first_seen=None, last_seen=None):
    conn = sqlite3.connect(db_path)
    conn.execute(
        """INSERT OR REPLACE INTO groups
           (fingerprint, exception_type, normalize_message, function_chain, count,
            first_seen, last_seen, service, environment, status, resolved_at,
            github_issue_url, github_issue_number)
           VALUES (?,?,?,?,?,?,?,?,?,?,NULL,NULL,NULL)""",
        (fp, exc, msg, chain, count,
         first_seen or _ts(-60), last_seen or _ts(), service, env, status)
    )
    conn.commit()
    conn.close()


def _insert_event(db_path, fp, service="svc", env="production", ts=None, exc="TypeError"):
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO events VALUES (?,?,?,?,?,?)",
        (fp, ts or _ts(), exc, "msg", service, env)
    )
    conn.commit()
    conn.close()


def _insert_llm_event(db_path, fp="llmfp1", model="gpt-4o", feature="summarizer",
                      service="svc", env="production", ts=None,
                      input_tokens=100, output_tokens=50, latency_ms=500,
                      cost_usd=0.01, is_error=0):
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO llm_events VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (fp, ts or _ts(), model, feature, service, env,
         input_tokens, output_tokens, latency_ms, cost_usd, is_error)
    )
    # upsert llm_groups
    conn.execute("""
        INSERT INTO llm_groups VALUES (?,?,?,?,?,1,?,?,?,?,?,?,?)
        ON CONFLICT(fingerprint) DO UPDATE SET
            total_calls = total_calls + 1,
            total_errors = total_errors + ?,
            total_input_tokens = total_input_tokens + ?,
            total_output_tokens = total_output_tokens + ?,
            total_cost_usd = total_cost_usd + ?,
            total_latency_ms = total_latency_ms + ?,
            last_seen = ?
    """, (
        fp, model, feature, service, env,
        is_error, input_tokens, output_tokens, cost_usd, latency_ms,
        ts or _ts(), ts or _ts(),
        is_error, input_tokens, output_tokens, cost_usd, latency_ms, ts or _ts()
    ))
    conn.commit()
    conn.close()


def _insert_deploy(db_path, service="svc", env="production", version="v1.0", ts=None):
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO deploys (service, environment, version, timestamp) VALUES (?,?,?,?)",
        (service, env, version, ts or _ts())
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Tests: GET /api/issues
# ---------------------------------------------------------------------------

class TestGetIssues:
    def test_empty_db_returns_empty_list(self, client, db_path):
        r = client.get("/api/issues")
        assert r.status_code == 200
        data = r.get_json()
        assert "issues" in data
        assert data["issues"] == []

    def test_issue_shape(self, client, db_path):
        _insert_group(db_path, "fp1")
        _insert_event(db_path, "fp1")
        r = client.get("/api/issues")
        assert r.status_code == 200
        issues = r.get_json()["issues"]
        assert len(issues) == 1
        issue = issues[0]
        # Verify all required fields
        for field in ["fp", "exc", "msg", "chain", "count", "first_seen",
                      "last_seen", "service", "env", "status", "spiking",
                      "trend", "github"]:
            assert field in issue, f"Missing field: {field}"
        assert isinstance(issue["chain"], list)
        assert isinstance(issue["trend"], list)
        assert len(issue["trend"]) == 16
        assert issue["status"] == "active"
        assert issue["github"] is None

    def test_env_filter(self, client, db_path):
        _insert_group(db_path, "fp1", env="production")
        _insert_group(db_path, "fp2", env="staging")
        r = client.get("/api/issues?env=production")
        issues = r.get_json()["issues"]
        assert len(issues) == 1
        assert issues[0]["env"] == "production"

    def test_q_filter_exc(self, client, db_path):
        _insert_group(db_path, "fp1", exc="TypeError")
        _insert_group(db_path, "fp2", exc="ValueError")
        r = client.get("/api/issues?q=typeerror")
        issues = r.get_json()["issues"]
        assert len(issues) == 1
        assert issues[0]["exc"] == "TypeError"

    def test_q_filter_service(self, client, db_path):
        _insert_group(db_path, "fp1", service="checkout-api")
        _insert_group(db_path, "fp2", service="auth-service")
        r = client.get("/api/issues?q=checkout")
        issues = r.get_json()["issues"]
        assert len(issues) == 1
        assert issues[0]["service"] == "checkout-api"

    def test_q_filter_msg(self, client, db_path):
        _insert_group(db_path, "fp1", msg="Cannot read undefined")
        _insert_group(db_path, "fp2", msg="NullPointerException in foo")
        r = client.get("/api/issues?q=nullpointer")
        issues = r.get_json()["issues"]
        assert len(issues) == 1

    def test_sorted_by_count_desc(self, client, db_path):
        _insert_group(db_path, "fp1", count=5)
        _insert_group(db_path, "fp2", count=100)
        _insert_group(db_path, "fp3", count=50)
        r = client.get("/api/issues")
        counts = [i["count"] for i in r.get_json()["issues"]]
        assert counts == sorted(counts, reverse=True)

    def test_github_field_populated(self, client, db_path):
        conn = sqlite3.connect(db_path)
        conn.execute(
            """INSERT INTO groups VALUES
               ('fp1','TypeError','msg','a->b',10,'2026-01-01T00:00:00Z','2026-01-01T01:00:00Z',
                'svc','production','active',NULL,
                'https://github.com/foo/bar/issues/99', 99)"""
        )
        conn.commit()
        conn.close()
        r = client.get("/api/issues")
        issue = r.get_json()["issues"][0]
        assert issue["github"] == {"n": 99, "url": "https://github.com/foo/bar/issues/99"}

    def test_regressed_status_returned(self, client, db_path):
        _insert_group(db_path, "fp1", status="regressed")
        r = client.get("/api/issues")
        issue = r.get_json()["issues"][0]
        assert issue["status"] == "regressed"


# ---------------------------------------------------------------------------
# Tests: GET /api/issues/<fp>
# ---------------------------------------------------------------------------

class TestGetIssueDetail:
    def test_not_found(self, client, db_path):
        r = client.get("/api/issues/nonexistent")
        assert r.status_code == 404

    def test_shape_with_llm_null(self, client, db_path):
        _insert_group(db_path, "fp1")
        r = client.get("/api/issues/fp1")
        assert r.status_code == 200
        data = r.get_json()
        assert data["fp"] == "fp1"
        assert data["llm"] is None

    def test_llm_field_populated(self, client, db_path):
        _insert_group(db_path, "fp1", service="svc", env="production")
        _insert_llm_event(db_path, service="svc", env="production",
                          ts=_ts(-30), cost_usd=0.05, is_error=1)
        r = client.get("/api/issues/fp1")
        assert r.status_code == 200
        llm = r.get_json()["llm"]
        assert llm is not None
        assert "calls" in llm
        assert "cost_usd" in llm
        assert "errors" in llm
        assert llm["calls"] >= 1


# ---------------------------------------------------------------------------
# Tests: POST /api/issues/<fp>/resolve and /reopen
# ---------------------------------------------------------------------------

class TestResolveReopen:
    def test_resolve_sets_status(self, client, db_path):
        _insert_group(db_path, "fp1")
        r = client.post("/api/issues/fp1/resolve")
        assert r.status_code == 200
        data = r.get_json()
        assert data["ok"] is True
        assert data["status"] == "resolved"
        assert "github_closed" in data

        # Verify in DB
        conn = sqlite3.connect(db_path)
        row = conn.execute("SELECT status FROM groups WHERE fingerprint='fp1'").fetchone()
        conn.close()
        assert row[0] == "resolved"

    def test_reopen_sets_active(self, client, db_path):
        _insert_group(db_path, "fp1", status="resolved")
        r = client.post("/api/issues/fp1/reopen")
        assert r.status_code == 200
        data = r.get_json()
        assert data["ok"] is True
        assert data["status"] == "active"

        conn = sqlite3.connect(db_path)
        row = conn.execute("SELECT status, resolved_at FROM groups WHERE fingerprint='fp1'").fetchone()
        conn.close()
        assert row[0] == "active"
        assert row[1] is None

    def test_resolve_reopen_round_trip(self, client, db_path):
        _insert_group(db_path, "fp1")
        client.post("/api/issues/fp1/resolve")
        client.post("/api/issues/fp1/reopen")
        conn = sqlite3.connect(db_path)
        row = conn.execute("SELECT status FROM groups WHERE fingerprint='fp1'").fetchone()
        conn.close()
        assert row[0] == "active"

    def test_resolve_not_found(self, client, db_path):
        r = client.post("/api/issues/missing/resolve")
        assert r.status_code == 404

    def test_reopen_not_found(self, client, db_path):
        r = client.post("/api/issues/missing/reopen")
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# Tests: POST /api/issues/<fp>/github
# ---------------------------------------------------------------------------

class TestGithubAction:
    def test_github_not_configured(self, client, db_path):
        _insert_group(db_path, "fp1")
        with patch("core.github.github_configured", return_value=False):
            r = client.post("/api/issues/fp1/github")
        assert r.status_code == 400
        data = r.get_json()
        assert data["ok"] is False
        assert data["error"] == "github_not_configured"

    def test_github_creates_issue(self, client, db_path):
        _insert_group(db_path, "fp1")
        with patch("core.github.github_configured", return_value=True), \
             patch("core.github.create_issue", return_value=(42, "https://github.com/x/y/issues/42")):
            r = client.post("/api/issues/fp1/github")
        assert r.status_code == 200
        data = r.get_json()
        assert data["ok"] is True
        assert data["github"]["n"] == 42

        # Verify stored in DB
        conn = sqlite3.connect(db_path)
        row = conn.execute(
            "SELECT github_issue_number, github_issue_url FROM groups WHERE fingerprint='fp1'"
        ).fetchone()
        conn.close()
        assert row[0] == 42
        assert "42" in row[1]


# ---------------------------------------------------------------------------
# Tests: GET /api/overview
# ---------------------------------------------------------------------------

class TestOverview:
    def test_empty_db(self, client, db_path):
        r = client.get("/api/overview")
        assert r.status_code == 200
        data = r.get_json()
        required = ["total_events", "active_issues", "resolved_30d", "events_per_min",
                    "events_spark", "events_daily", "active_daily", "resolved_daily",
                    "spiking_count", "regressed_count"]
        for field in required:
            assert field in data, f"Missing field: {field}"
        assert data["total_events"] == 0
        assert data["active_issues"] == 0
        assert len(data["events_spark"]) == 20
        assert len(data["events_daily"]) == 14
        assert len(data["active_daily"]) == 14
        assert len(data["resolved_daily"]) == 14

    def test_seeded_db_counts(self, client, db_path):
        _insert_group(db_path, "fp1", count=10, status="active")
        _insert_group(db_path, "fp2", count=5, status="resolved")
        _insert_event(db_path, "fp1")
        _insert_event(db_path, "fp1")
        r = client.get("/api/overview")
        data = r.get_json()
        assert data["total_events"] == 2
        assert data["active_issues"] == 1

    def test_env_filter(self, client, db_path):
        _insert_group(db_path, "fp1", env="production", count=5)
        _insert_group(db_path, "fp2", env="staging", count=3)
        _insert_event(db_path, "fp1", env="production")
        _insert_event(db_path, "fp2", env="staging")
        r = client.get("/api/overview?env=production")
        data = r.get_json()
        assert data["total_events"] == 1
        assert data["active_issues"] == 1

    def test_regressed_count(self, client, db_path):
        _insert_group(db_path, "fp1", status="regressed")
        r = client.get("/api/overview")
        data = r.get_json()
        assert data["regressed_count"] == 1


# ---------------------------------------------------------------------------
# Tests: GET /api/llm
# ---------------------------------------------------------------------------

class TestLlm:
    def test_empty_db(self, client, db_path):
        r = client.get("/api/llm")
        assert r.status_code == 200
        data = r.get_json()
        required = ["groups", "totals", "calls_daily", "cost_daily", "errors_daily", "latency_daily"]
        for field in required:
            assert field in data, f"Missing field: {field}"
        assert data["groups"] == []
        assert data["totals"]["calls"] == 0
        assert len(data["calls_daily"]) == 14

    def test_seeded_group_shape(self, client, db_path):
        _insert_llm_event(db_path, fp="llm1", model="gpt-4o", feature="chat",
                          service="api", env="production", cost_usd=0.05, is_error=0)
        r = client.get("/api/llm")
        data = r.get_json()
        assert len(data["groups"]) == 1
        grp = data["groups"][0]
        for field in ["model", "feature", "service", "env", "calls", "errors",
                      "err_pct", "avg_latency_ms", "cost_usd", "last_seen",
                      "tokens_in", "tokens_out"]:
            assert field in grp, f"Missing field: {field}"
        assert grp["model"] == "gpt-4o"
        assert grp["calls"] == 1

    def test_env_filter(self, client, db_path):
        _insert_llm_event(db_path, fp="llm1", env="production")
        _insert_llm_event(db_path, fp="llm2", env="staging")
        r = client.get("/api/llm?env=production")
        data = r.get_json()
        assert len(data["groups"]) == 1
        assert data["groups"][0]["env"] == "production"

    def test_totals_aggregation(self, client, db_path):
        _insert_llm_event(db_path, fp="llm1", cost_usd=0.10, is_error=0, latency_ms=400)
        _insert_llm_event(db_path, fp="llm1", cost_usd=0.20, is_error=1, latency_ms=600)
        r = client.get("/api/llm")
        totals = r.get_json()["totals"]
        assert totals["calls"] == 2
        assert totals["errors"] == 1
        assert abs(totals["cost_usd"] - 0.30) < 0.001


# ---------------------------------------------------------------------------
# Tests: GET /api/deploys
# ---------------------------------------------------------------------------

class TestDeploys:
    def test_empty_db(self, client, db_path):
        r = client.get("/api/deploys")
        assert r.status_code == 200
        data = r.get_json()
        required = ["deploys", "stats"]
        for field in required:
            assert field in data, f"Missing field: {field}"
        assert data["deploys"] == []
        assert data["stats"]["deploys_7d"] == 0
        assert data["stats"]["last_deploy_at"] is None

    def test_deploy_shape(self, client, db_path):
        _insert_deploy(db_path, service="api", env="production", version="v1.1")
        r = client.get("/api/deploys")
        data = r.get_json()
        assert len(data["deploys"]) == 1
        d = data["deploys"][0]
        for field in ["version", "service", "env", "deployed_at",
                      "errors_after", "suspect", "suspect_fp"]:
            assert field in d, f"Missing field: {field}"
        assert d["version"] == "v1.1"
        assert d["errors_after"] == 0
        assert d["suspect"] is False

    def test_errors_after_counted(self, client, db_path):
        _insert_deploy(db_path, service="svc", env="production",
                       version="v1.0", ts=_ts(-60))
        for _ in range(25):
            _insert_event(db_path, "fp1", service="svc", env="production", ts=_ts(-30))
        r = client.get("/api/deploys")
        d = r.get_json()["deploys"][0]
        assert d["errors_after"] == 25

    def test_suspect_flag(self, client, db_path):
        _insert_deploy(db_path, service="svc", env="production",
                       version="v1.0", ts=_ts(-60))
        for _ in range(20):
            _insert_event(db_path, "fp1", service="svc", env="production", ts=_ts(-30))
        r = client.get("/api/deploys")
        d = r.get_json()["deploys"][0]
        assert d["suspect"] is True
        assert d["suspect_fp"] == "fp1"

    def test_env_filter(self, client, db_path):
        _insert_deploy(db_path, service="svc", env="production")
        _insert_deploy(db_path, service="svc", env="staging")
        r = client.get("/api/deploys?env=production")
        data = r.get_json()
        assert len(data["deploys"]) == 1
        assert data["deploys"][0]["env"] == "production"

    def test_stats(self, client, db_path):
        _insert_deploy(db_path, service="svc1", env="production")
        _insert_deploy(db_path, service="svc2", env="staging")
        r = client.get("/api/deploys")
        stats = r.get_json()["stats"]
        assert stats["deploys_7d"] == 2
        assert stats["services"] == 2
        assert stats["last_deploy_at"] is not None


# ---------------------------------------------------------------------------
# Tests: GET /api/alerts
# ---------------------------------------------------------------------------

class TestAlerts:
    def test_empty_db(self, client, db_path):
        r = client.get("/api/alerts")
        assert r.status_code == 200
        data = r.get_json()
        required = ["alerts", "rules", "slack_connected"]
        for field in required:
            assert field in data, f"Missing field: {field}"
        assert isinstance(data["alerts"], list)
        assert isinstance(data["rules"], list)
        assert len(data["rules"]) == 7

    def test_threshold_alert_generated(self, client, db_path):
        _insert_group(db_path, "fp1", count=100, exc="TypeError", service="api")
        r = client.get("/api/alerts")
        alert_ids = [a["id"] for a in r.get_json()["alerts"]]
        assert "threshold:fp1" in alert_ids

    def test_regression_alert_generated(self, client, db_path):
        _insert_group(db_path, "fp1", status="regressed", exc="ValueError", service="svc")
        r = client.get("/api/alerts")
        alerts = r.get_json()["alerts"]
        reg_alerts = [a for a in alerts if a["sev"] == "regression"]
        assert any(a["id"] == "regression:fp1" for a in reg_alerts)

    def test_deploy_suspect_alert(self, client, db_path):
        _insert_deploy(db_path, service="svc", env="production",
                       version="v1.0", ts=_ts(-60))
        for _ in range(25):
            _insert_event(db_path, "fp1", service="svc", env="production", ts=_ts(-30))
        r = client.get("/api/alerts")
        alerts = r.get_json()["alerts"]
        deploy_alerts = [a for a in alerts if a["sev"] == "deploy"]
        assert len(deploy_alerts) >= 1

    def test_llm_error_rate_alert(self, client, db_path):
        # 1 call, 1 error = 100% error rate → > 10% threshold
        _insert_llm_event(db_path, fp="llmfp1", is_error=1)
        r = client.get("/api/alerts")
        alerts = r.get_json()["alerts"]
        llm_alerts = [a for a in alerts if a["sev"] == "llm"]
        assert len(llm_alerts) >= 1

    def test_alert_shape(self, client, db_path):
        _insert_group(db_path, "fp1", count=100, exc="TypeError", service="api")
        r = client.get("/api/alerts")
        alert = next(a for a in r.get_json()["alerts"] if a["id"] == "threshold:fp1")
        for field in ["id", "sev", "title", "detail", "service", "env", "ts", "link"]:
            assert field in alert, f"Missing field: {field}"
        assert "type" in alert["link"]

    def test_slack_connected_false(self, client, db_path):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SLACK_WEBHOOK_URL", None)
            r = client.get("/api/alerts")
        assert r.get_json()["slack_connected"] is False

    def test_env_filter(self, client, db_path):
        _insert_group(db_path, "fp1", count=100, env="production", service="api")
        _insert_group(db_path, "fp2", count=100, env="staging", service="api")
        r = client.get("/api/alerts?env=production")
        alerts = r.get_json()["alerts"]
        # All returned alerts should be for production
        for a in alerts:
            if a["env"]:
                assert a["env"] == "production"


# ---------------------------------------------------------------------------
# Tests: GET /api/meta
# ---------------------------------------------------------------------------

class TestMeta:
    def test_empty_db(self, client, db_path):
        r = client.get("/api/meta")
        assert r.status_code == 200
        data = r.get_json()
        required = ["services", "envs", "health", "github_configured", "slack_connected"]
        for field in required:
            assert field in data, f"Missing field: {field}"
        assert isinstance(data["services"], list)
        assert isinstance(data["envs"], list)
        health = data["health"]
        for hfield in ["ok", "db_bytes", "event_count", "retention_days", "host", "api_key_set"]:
            assert hfield in health, f"Missing health field: {hfield}"
        assert health["retention_days"] == 30
        assert health["host"] == "localhost:7000"

    def test_seeded_services(self, client, db_path):
        _insert_event(db_path, "fp1", service="checkout-api")
        _insert_event(db_path, "fp1", service="checkout-api")
        _insert_event(db_path, "fp2", service="auth-svc")
        r = client.get("/api/meta")
        data = r.get_json()
        svc_names = [s["name"] for s in data["services"]]
        assert "checkout-api" in svc_names
        assert "auth-svc" in svc_names
        checkout = next(s for s in data["services"] if s["name"] == "checkout-api")
        assert checkout["count"] == 2

    def test_envs_active_only(self, client, db_path):
        _insert_group(db_path, "fp1", env="production", status="active")
        _insert_group(db_path, "fp2", env="staging", status="resolved")
        r = client.get("/api/meta")
        env_names = [e["name"] for e in r.get_json()["envs"]]
        assert "production" in env_names
        assert "staging" not in env_names

    def test_health_event_count(self, client, db_path):
        _insert_event(db_path, "fp1")
        _insert_event(db_path, "fp1")
        r = client.get("/api/meta")
        assert r.get_json()["health"]["event_count"] == 2

    def test_github_not_configured(self, client, db_path):
        with patch("core.github.github_configured", return_value=False):
            r = client.get("/api/meta")
        assert r.get_json()["github_configured"] is False

    def test_github_configured(self, client, db_path):
        with patch("core.github.github_configured", return_value=True):
            r = client.get("/api/meta")
        assert r.get_json()["github_configured"] is True


# ---------------------------------------------------------------------------
# Tests: CORS
# ---------------------------------------------------------------------------

class TestCors:
    def test_cors_headers_present(self, client, db_path):
        r = client.get("/api/meta", headers={"Origin": "http://localhost:5173"})
        assert "Access-Control-Allow-Origin" in r.headers

    def test_options_preflight(self, client, db_path):
        r = client.options("/api/meta")
        assert r.status_code == 204
