import sqlite3
from fingerprinting import fingerprint
from normalize import normalize_message

#connecting the db, must create one if we dont have it yet,creations happen in connect
conn = sqlite3.connect('errscope.db')

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
            last_seen TEXT
            )''')


#table for events will change when doing in golang 
cur.execute('''
CREATE TABLE IF NOT EXISTS events(
            fingerprint TEXT,
            timestamp TEXT,
            exception_type TEXT,
            message TEXT
            )''')

conn.commit()


def store_event(event):
    fp = fingerprint(event)
    norm_msg = normalize_message(event["message"])
    fn_chain = "->".join(frame["function"] for frame in event["stack_trace"])

    #updates if the ven is already in groups adds 1 and changes latest time
    cur.execute("INSERT INTO events VALUES (?, ?, ?, ?)", (fp, event["timestamp"], event["exception_type"], event["message"]))
    cur.execute("""
        INSERT INTO groups VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(fingerprint) DO UPDATE SET
            count = count + 1,
            last_seen = ?
    """, (fp, event["exception_type"], norm_msg, fn_chain, 1, event["timestamp"], event["timestamp"], event["timestamp"])) 
    #makes just the changes are commited and not lost
    conn.commit()

