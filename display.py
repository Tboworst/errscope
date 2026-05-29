import sqlite3
from datetime import datetime
from rich.console import Console
from rich.table import Table


# Console is the Rich object that handles printing to the terminal with colour
console = Console()

# Connect to the same database file that storage.py writes to
conn = sqlite3.connect('errscope.db')


def format_timestamp(ts):
    # Timestamps are stored as ISO 8601 strings e.g. "2024-01-15T10:23:45Z"
    # We parse them and return a short human-readable format e.g. "Jan 15 10:23"
    dt = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ")
    return dt.strftime("%b %d %H:%M")


def show_groups():
    # Build the Rich table with a title shown at the top
    table = Table(title="ErrScope — Live Error Groups")

    # Each column gets a name and a colour style
    # Count is the most important column — yellow makes it stand out
    table.add_column("#", style="bold white")
    table.add_column("Exception", style="red")
    table.add_column("Message", style="cyan")
    table.add_column("Count", style="yellow")
    table.add_column("First Seen", style="green")
    table.add_column("Last Seen", style="green")

    cur = conn.cursor()

    # Fetch all groups sorted by count descending so the most frequent errors
    # are always at the top — this stays fast even with thousands of groups
    rows = cur.execute("""
        SELECT exception_type, normalize_message, count, first_seen, last_seen
        FROM groups
        ORDER BY count DESC
    """).fetchall()

    for i, row in enumerate(rows, start=1):
        exception_type, message, count, first_seen, last_seen = row

        # Truncate long messages so the table stays readable
        short_message = message[:50] + "..." if len(message) > 50 else message

        # Format timestamps from ISO 8601 to a short readable form
        table.add_row(
            str(i),
            exception_type,
            short_message,
            str(count),
            format_timestamp(first_seen),
            format_timestamp(last_seen),
        )

    return table


if __name__ == "__main__":
    show_groups()
