# Beacon

**Self-hosted error tracking and monitoring for developers who want control.**

Beacon ingests errors from any service, groups them by root cause, and surfaces everything in a live terminal dashboard — no third-party service, no data leaving your infrastructure, no monthly bill.

Think lightweight Sentry, built for the terminal, owned by you.

---

## What it looks like

```
 beacon  live error monitoring
┌─ error groups ─────────────────────────────────┐ ┌─ overview ────────┐
│ #  exception        message           count     │ │ total events      │
│ 1  AttributeError   NoneType has no…    142     │ │ 186               │
│ 2  KeyError         Missing key use…     38     │ │                   │
│ 3  ValueError       invalid literal…     12     │ │ unique groups     │
│                                                 │ │ 3                 │
│                                                 │ │                   │
│                                                 │ │ events / min      │
│                                                 │ │ ▁▂▃▅▇█▅▃▂▁       │
└─────────────────────────────────────────────────┘ └───────────────────┘
 q quit  r refresh  enter details
```

Press **enter** on any row to drill into the full stack trace, call chain, and timestamps.

---

## Quick start — Docker

```bash
git clone https://github.com/Tboworst/beacon.git
cd beacon
cp .env.example .env   # add your API key and Slack webhook
docker-compose up
```

Server is running at `http://localhost:7000`.

Open the dashboard in a separate terminal:

```bash
pip install textual
python3 start_dashboard.py
```

---

## Quick start — without Docker

```bash
git clone https://github.com/Tboworst/beacon.git
cd beacon
pip install -r requirements.txt
cp .env.example .env
python3 start_server.py      # terminal 1
python3 start_dashboard.py   # terminal 2
```

---

## Python SDK

Install in your app:

```bash
pip install requests
```

Copy `sdk/python/beacon/` into your project, then add two lines to your entry point:

```python
import beacon

beacon.init(
    endpoint="http://your-beacon-server:7000/ingest",
    service="my-app",
    environment="production",
    api_key="your-secret-key-here"   # matches BEACON_API_KEY in .env
)
```

Every unhandled exception is now automatically captured. For handled exceptions:

```python
try:
    risky_operation()
except Exception as e:
    beacon.capture(e)
```

---

## Configuration

| Variable | Description |
|---|---|
| `BEACON_API_KEY` | Secret key required on all ingest requests. If not set, server accepts all requests (local dev mode). |
| `SLACK_WEBHOOK_URL` | Slack incoming webhook URL. Alerts fire when an error group crosses the threshold. |

---

## How errors are grouped

```
raw errors:  "NoneType has no attribute 'email'"
             "NoneType has no attribute 'username'"

fingerprint: AttributeError
             NoneType has no attribute <attr>        ← normalized
             handle_request → get_current_user → find_user_by_token

result:      same group. one bug. one row.
```

Fingerprint = hash of exception type + normalized message + function call chain.
Line numbers are ignored — they change on every reformat. Function names are stable.

---

## Project structure

```
beacon/
├── core/               ← ingest server, storage, fingerprinting (Python → Go)
├── dashboard/          ← live TUI dashboard (Textual)
├── sdk/
│   └── python/         ← Python SDK
├── start_server.py     ← python3 start_server.py
├── start_dashboard.py  ← python3 start_dashboard.py
├── docker-compose.yml
└── requirements.txt
```

---

## Sending errors from any language

Any service can send errors directly over HTTP — no SDK required:

```bash
curl -X POST http://localhost:7000/ingest \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: your-secret-key-here" \
  -d '{
    "timestamp": "2024-01-15T10:23:45Z",
    "exception_type": "AttributeError",
    "message": "NoneType object has no attribute email",
    "stack_trace": [
      {"function": "handle_request", "file": "/app/server.py", "line": 42},
      {"function": "get_current_user", "file": "/app/auth.py", "line": 87}
    ]
  }'
```

---

## Roadmap

- [ ] Deploy markers — correlate errors with deploys
- [ ] Environment tagging — separate prod vs staging
- [ ] Spike detection — alert on rate of increase, not just total count
- [ ] Regression alerts — error quiet for 7 days that suddenly fires again
- [ ] Resolve / ignore groups from the TUI
- [ ] GitHub issue creation from any error group
- [ ] Node.js SDK
- [ ] Go rewrite of the core server with Redis hot path

---

## Stack

| Layer | Tech |
|---|---|
| Ingest server | Python + Flask |
| Storage | SQLite |
| Dashboard | Python + Textual |
| Alerts | Slack webhooks |
| Containerisation | Docker |

---

## Why not just use Sentry?

Sentry is excellent. Beacon is for when you want:
- No data leaving your network
- No per-event pricing at scale
- A terminal-native workflow
- Something you can read, modify, and own completely

---

Built in public. Stars appreciated.
