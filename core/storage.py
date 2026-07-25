import sqlite3
from .fingerprinting import fingerprint
from .normalize import normalize_message
from .alerts import check_and_alert, check_spike, alert_regression, check_correlated_spike

#connecting the db, must create one if we dont have it yet,creations happen in connect
conn = sqlite3.connect('beacon.db')

#create a cursor object that runs the sql commands
cur = conn.cursor()

#table for groups
cur.execute('''
CREATE TABLE IF NOT EXISTS groups(
            fingerprint TEXT PRIMARY KEY,
            exception_type TEXT,
            normalize_message TEXT,
            function_chain TEXT,
            count INTEGER,
            first_seen TEXT,
            last_seen TEXT,
            service TEXT,
            environment TEXT
            )''')


#table for events will change when doing in golang
cur.execute('''
CREATE TABLE IF NOT EXISTS events(
            fingerprint TEXT,
            timestamp TEXT,
            exception_type TEXT,
            message TEXT,
            service TEXT,
            environment TEXT
            )''')

conn.commit()

# Migration: add columns to existing databases
for _col_sql in [
    "ALTER TABLE groups ADD COLUMN status TEXT DEFAULT 'active'",
    "ALTER TABLE groups ADD COLUMN resolved_at TEXT",
    "ALTER TABLE groups ADD COLUMN github_issue_url TEXT",
    "ALTER TABLE groups ADD COLUMN github_issue_number INTEGER",
]:
    try:
        cur.execute(_col_sql)
        conn.commit()
    except sqlite3.OperationalError:
        pass  # column already exists


def resolve_group(fp):
    """Mark an error group as resolved. If the same error fires again, a regression alert is sent."""
    local_conn = sqlite3.connect('beacon.db')
    local_conn.execute(
        "UPDATE groups SET status = 'resolved', resolved_at = datetime('now') WHERE fingerprint = ?",
        (fp,)
    )
    local_conn.commit()
    local_conn.close()


def store_event(event):
    fp = fingerprint(event)
    norm_msg = normalize_message(event["message"])
    fn_chain = "->".join(frame["function"] for frame in event["stack_trace"])
    service = event.get("service") or "unknown"
    environment = event.get("environment") or "unknown"

    # open a new connection per call so this is safe to call from any thread
    # SQLite connections cannot be shared across threads
    local_conn = sqlite3.connect('beacon.db')
    local_cur = local_conn.cursor()

    # Regression detection: check current status before the upsert so we know
    # if this event is a recurrence of something the user already marked resolved
    existing = local_cur.execute(
        "SELECT status FROM groups WHERE fingerprint = ?", (fp,)
    ).fetchone()
    was_resolved = existing is not None and existing[0] == 'resolved'

    local_cur.execute("INSERT INTO events VALUES (?, ?, ?, ?, ?, ?)", (fp, event["timestamp"], event["exception_type"], event["message"], service, environment))

    # Upsert group — if it was resolved, mark it as regressed and clear resolved_at
    local_cur.execute("""
        INSERT INTO groups VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', NULL)
        ON CONFLICT(fingerprint) DO UPDATE SET
            count = count + 1,
            last_seen = ?,
            status = CASE WHEN status = 'resolved' THEN 'regressed' ELSE status END,
            resolved_at = CASE WHEN status = 'resolved' THEN NULL ELSE resolved_at END
    """, (fp, event["exception_type"], norm_msg, fn_chain, 1, event["timestamp"], event["timestamp"], service, environment, event["timestamp"]))

    #makes sure the changes are committed and not lost
    local_conn.commit()

    # If this is a regression, fire the regression alert immediately
    if was_resolved:
        grp = local_cur.execute(
            "SELECT exception_type, service, environment FROM groups WHERE fingerprint = ?", (fp,)
        ).fetchone()
        if grp:
            alert_regression(fp, grp[0], grp[1], grp[2])

    # check after commit so the count in the DB is already updated
    row = local_cur.execute("SELECT count FROM groups WHERE fingerprint = ?", (fp,)).fetchone()
    check_and_alert(fp, row[0])

    # spike check: compare the last 5 minutes against the previous 5 minutes
    # fires a separate Slack alert if the rate jumped 5x or more
    check_spike(fp)

    # correlation check: if both error rate and LLM cost spiked for this
    # service at the same time, fire a single combined alert
    check_correlated_spike(service, environment)

    # drop raw events older than 30 days — groups are kept forever
    local_cur.execute("DELETE FROM events WHERE timestamp < datetime('now', '-30 days')")
    local_conn.commit()

    local_conn.close()

