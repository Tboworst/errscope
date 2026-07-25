import sqlite3

DB_PATH = "beacon.db"

conn = sqlite3.connect(DB_PATH)
conn.execute("""
    CREATE TABLE IF NOT EXISTS deploys (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        service TEXT,
        environment TEXT,
        version TEXT,
        timestamp TEXT
    )
""")
conn.commit()
conn.close()


def store_deploy(data):
    service = data.get("service") or "unknown"
    environment = data.get("environment") or "unknown"
    version = data.get("version") or "unknown"
    timestamp = data.get("timestamp") or ""

    local_conn = sqlite3.connect(DB_PATH)
    local_conn.execute(
        "INSERT INTO deploys (service, environment, version, timestamp) VALUES (?, ?, ?, ?)",
        (service, environment, version, timestamp)
    )
    local_conn.commit()
    local_conn.close()
