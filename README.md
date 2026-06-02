# errscope

**Self-hosted error tracking and monitoring for developers who want control.**

errscope ingests errors from any service, groups them by root cause, and surfaces everything in a live terminal dashboard — no third-party service, no data leaving your infrastructure, no monthly bill.

Think lightweight Sentry, built for the terminal, owned by you.

---

## What it looks like

```
 errscope  live error monitoring
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

Press **enter** on any row to see the full stack trace, call chain, and timestamps.

---

## Features

- **Smart grouping** — errors are grouped by what caused them, not raw message text. `NoneType has no attribute 'email'` and `NoneType has no attribute 'username'` land in the same group because they're the same bug.
- **Fingerprinting** — exception type + normalized message + function call chain. Line numbers are ignored (they change when you reformat code). Function names are the stable identity of where something broke.
- **Normalization** — runtime noise stripped before hashing: file paths, UUIDs, emails, numbers all replaced with placeholders so the same bug always produces the same fingerprint.
- **HTTP ingest** — any service can send errors with a single POST request. Language agnostic.
- **Live TUI dashboard** — real-time updating terminal UI built with Textual. Sparkline showing event rate over the last 20 minutes.
- **Slack alerts** — automatic notification when an error group crosses a threshold.
- **30-day retention** — raw events older than 30 days are pruned automatically. Error groups and counts are kept forever.
- **Self-hosted** — your errors stay on your infrastructure.

---

## Quick start

```bash
git clone https://github.com/Tboworst/errscope.git
cd errscope
pip install flask watchdog textual requests
```

Set your Slack webhook (optional):

```bash
cp .env.example .env
# edit .env and add your SLACK_WEBHOOK_URL
```

Start the ingest server:

```bash
python3 server.py
```

Open the dashboard in a new terminal:

```bash
python3 dashboard.py
```

Send an error from any service:

```bash
curl -X POST http://localhost:7000/ingest \
  -H "Content-Type: application/json" \
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

Watch it appear in the dashboard instantly.

---

## How errors are grouped

```
raw error:   "NoneType has no attribute 'email'"
             "NoneType has no attribute 'username'"

fingerprint: AttributeError
             NoneType has no attribute <attr>        ← normalized
             handle_request → get_current_user → find_user_by_token

result:      same group. one bug. one row.
```

The fingerprint is a SHA-256 hash of exception type + normalized message + function call chain.

---

## Sending errors from your app

Any language, any framework. Just POST JSON:

```python
# Python
import requests, traceback, datetime

def capture(exc):
    requests.post("http://localhost:7000/ingest", json={
        "timestamp": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "exception_type": type(exc).__name__,
        "message": str(exc),
        "stack_trace": [
            {"function": frame.name, "file": frame.filename, "line": frame.lineno}
            for frame in traceback.extract_tb(exc.__traceback__)
        ]
    })
```

```javascript
// Node.js
function capture(err) {
  fetch("http://localhost:7000/ingest", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      timestamp: new Date().toISOString().replace(".000Z", "Z"),
      exception_type: err.constructor.name,
      message: err.message,
      stack_trace: [{ function: "main", file: "app.js", line: 0 }]
    })
  })
}
```

---

## Roadmap

- [ ] Deploy markers — correlate errors with deploys ("started 3 min after deploy #12")
- [ ] Environment tagging — separate prod vs staging noise
- [ ] Spike detection — alert on rate of increase, not just total count
- [ ] Regression alerts — error quiet for 7 days that suddenly fires again
- [ ] Interactive resolution — mark groups as resolved or ignored from the TUI
- [ ] GitHub integration — open an issue from any error group with one keypress
- [ ] Go rewrite of the core — for high-throughput ingest with Redis hot path
- [ ] Multi-source dashboard — see all services in one view with source labels

---

## Stack

| Layer | Tech |
|---|---|
| Ingest | Python + Flask |
| Storage | SQLite |
| Dashboard | Python + Textual |
| Alerts | Slack webhooks |
| File watching | watchdog |

---

## Why not just use Sentry?

Sentry is excellent. errscope is for when you want:
- No data leaving your network
- No per-event pricing at scale
- A terminal-native workflow
- Something you actually understand and can modify

---

Built in public. Stars appreciated.
