import sqlite3
from .fingerprinting import fingerprint
from .normalize import normalize_message
from .alerts import check_and_alert, check_spike

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

    #updates if the event is already in groups adds 1 and changes latest time
    local_cur.execute("INSERT INTO events VALUES (?, ?, ?, ?, ?, ?)", (fp, event["timestamp"], event["exception_type"], event["message"], service, environment))
    local_cur.execute("""
        INSERT INTO groups VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(fingerprint) DO UPDATE SET
            count = count + 1,
            last_seen = ?
    """, (fp, event["exception_type"], norm_msg, fn_chain, 1, event["timestamp"], event["timestamp"], service, environment, event["timestamp"]))

    #makes sure the changes are committed and not lost
    local_conn.commit()

    # check after commit so the count in the DB is already updated
    row = local_cur.execute("SELECT count FROM groups WHERE fingerprint = ?", (fp,)).fetchone()
    check_and_alert(fp, row[0])

    # spike check: compare the last 5 minutes against the previous 5 minutes
    # fires a separate Slack alert if the rate jumped 5x or more
    check_spike(fp)

    # drop raw events older than 30 days — groups are kept forever
    local_cur.execute("DELETE FROM events WHERE timestamp < datetime('now', '-30 days')")
    local_conn.commit()

    local_conn.close()

