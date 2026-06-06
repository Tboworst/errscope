import sqlite3
from datetime import datetime

from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import DataTable, Footer, Header, Label, Sparkline, Static

DB_PATH = "beacon.db"


# ── DB helpers ────────────────────────────────────────────────────────────────
# each function opens its own connection so they are safe to call from any context

def fetch_groups(env_filter=None):
    try:
        conn = sqlite3.connect(DB_PATH)
        if env_filter:
            rows = conn.execute("""
                SELECT fingerprint, exception_type, normalize_message,
                       function_chain, count, first_seen, last_seen, service, environment
                FROM groups
                WHERE environment = ?
                ORDER BY count DESC
            """, (env_filter,)).fetchall()
        else:
            rows = conn.execute("""
                SELECT fingerprint, exception_type, normalize_message,
                       function_chain, count, first_seen, last_seen, service, environment
                FROM groups
                ORDER BY count DESC
            """).fetchall()
        conn.close()
        return rows
    except sqlite3.OperationalError:
        # DB doesn't exist yet or tables not created — return empty until server starts
        return []


def fetch_group_by_fingerprint(fp):
    try:
        conn = sqlite3.connect(DB_PATH)
        row = conn.execute("""
            SELECT fingerprint, exception_type, normalize_message,
                   function_chain, count, first_seen, last_seen, service, environment
            FROM groups WHERE fingerprint = ?
        """, (fp,)).fetchone()
        conn.close()
        return row
    except sqlite3.OperationalError:
        return None


def fetch_environments():
    try:
        conn = sqlite3.connect(DB_PATH)
        rows = conn.execute("""
            SELECT DISTINCT environment FROM groups
            WHERE environment IS NOT NULL
            ORDER BY environment
        """).fetchall()
        conn.close()
        return [r[0] for r in rows]
    except sqlite3.OperationalError:
        return []


def fetch_stats():
    try:
        conn = sqlite3.connect(DB_PATH)

        total_events = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        total_groups = conn.execute("SELECT COUNT(*) FROM groups").fetchone()[0]

        # count events per minute for the last 20 minutes to power the sparkline
        rate_rows = conn.execute("""
            SELECT COUNT(*)
            FROM events
            WHERE timestamp >= datetime('now', '-20 minutes')
            GROUP BY strftime('%Y-%m-%dT%H:%M', timestamp)
            ORDER BY strftime('%Y-%m-%dT%H:%M', timestamp)
        """).fetchall()

        conn.close()
        sparkline_data = [float(r[0]) for r in rate_rows]
        return total_events, total_groups, sparkline_data
    except sqlite3.OperationalError:
        # DB doesn't exist yet — return zeros until server starts
        return 0, 0, []


def fmt_ts(ts):
    try:
        return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").strftime("%b %d %H:%M")
    except Exception:
        return ts


# ── Detail modal ──────────────────────────────────────────────────────────────

class DetailModal(ModalScreen):
    """Shown when the user presses enter on an error group row."""

    BINDINGS = [("escape", "dismiss", "Close")]

    def __init__(self, row):
        super().__init__()
        self.row = row

    def compose(self) -> ComposeResult:
        fp, exc_type, norm_msg, fn_chain, count, first_seen, last_seen, service, environment = self.row

        # each step in the call chain gets its own line for readability
        chain_lines = "\n  ".join(fn_chain.split("->"))

        env_color = "red" if environment == "production" else "yellow"

        yield Vertical(
            Label(f"[bold red]{exc_type}[/bold red]", id="modal-title"),
            Static(""),
            Label(f"[dim]service[/dim]     {service}   [dim]env[/dim]  [{env_color}]{environment}[/{env_color}]"),
            Static(""),
            Label(f"[dim]message[/dim]"),
            Label(f"  {norm_msg}"),
            Static(""),
            Label(f"[dim]call chain[/dim]"),
            Label(f"  {chain_lines}"),
            Static(""),
            Label(f"[dim]count[/dim]       [yellow]{count}[/yellow]"),
            Label(f"[dim]first seen[/dim]  [green]{fmt_ts(first_seen)}[/green]"),
            Label(f"[dim]last seen[/dim]   [green]{fmt_ts(last_seen)}[/green]"),
            Static(""),
            Label(f"[dim]{fp}[/dim]"),
            Static(""),
            Label("[dim]ESC to close[/dim]"),
            id="modal-box",
        )


# ── Main app ──────────────────────────────────────────────────────────────────

class BeaconApp(App):

    CSS = """
    Screen {
        background: #080c10;
    }

    Header {
        background: #0d1f33;
        color: #a5d6ff;
    }

    Footer {
        background: #0d1f33;
        color: #79c0ff;
    }

    #body {
        height: 1fr;
        padding: 0 1;
    }

    #left-panel {
        width: 3fr;
        border: solid #58a6ff;
        padding: 0 1;
    }

    #right-panel {
        width: 1fr;
        border: solid #58a6ff;
        padding: 1 2;
        margin-left: 1;
    }

    #panel-title {
        color: #a5d6ff;
        text-style: bold;
        margin-bottom: 1;
    }

    #stats {
        height: auto;
        margin-bottom: 1;
    }

    #sparkline-label {
        color: #79c0ff;
        margin-top: 1;
        margin-bottom: 0;
    }

    Sparkline {
        height: 8;
    }

    Sparkline > .sparkline--max-color {
        color: #ff7b72;
    }

    Sparkline > .sparkline--min-color {
        color: #56d364;
    }

    DataTable {
        background: #080c10;
        color: #e6edf3;
    }

    DataTable > .datatable--header {
        background: #0d1f33;
        color: #a5d6ff;
        text-style: bold;
    }

    DataTable > .datatable--cursor {
        background: #388bfd;
        color: #ffffff;
    }

    /* detail modal */
    DetailModal {
        align: center middle;
    }

    #modal-box {
        background: #0d1f33;
        border: solid #a5d6ff;
        padding: 2 4;
        width: 65%;
        height: auto;
    }

    #modal-title {
        text-style: bold;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "manual_refresh", "Refresh"),
        Binding("e", "cycle_env", "Env filter"),
    ]

    TITLE = "beacon"
    SUB_TITLE = "all environments"

    env_filter: str | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="body"):
            with Vertical(id="left-panel"):
                yield Label("error groups", id="panel-title")
                yield DataTable(id="groups-table")
            with Vertical(id="right-panel"):
                yield Label("overview", id="panel-title")
                yield Static(id="stats")
                yield Label("events / min  (last 20m)", id="sparkline-label")
                yield Sparkline([], id="sparkline", summary_function=max)
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#groups-table", DataTable)
        table.cursor_type = "row"
        table.add_columns("#", "exception", "message", "count", "service", "env", "last seen")

        # initial load then refresh every 2 seconds
        self.refresh_data()
        self.set_interval(2, self.refresh_data)

    def refresh_data(self) -> None:
        self._update_table()
        self._update_stats()

    def _update_table(self) -> None:
        table = self.query_one("#groups-table", DataTable)
        table.clear()

        for i, row in enumerate(fetch_groups(self.env_filter), start=1):
            _, exc_type, norm_msg, _, count, _, last_seen, service, environment = row

            short_msg = norm_msg[:30] + "…" if len(norm_msg) > 30 else norm_msg

            # colour count by severity: red when high, yellow when moderate
            if count >= 50:
                count_display = f"[bold red]{count}[/bold red]"
            elif count >= 10:
                count_display = f"[yellow]{count}[/yellow]"
            else:
                count_display = str(count)

            env_display = f"[red]{environment}[/red]" if environment == "production" else f"[yellow]{environment}[/yellow]"

            table.add_row(
                str(i),
                f"[red]{exc_type}[/red]",
                short_msg,
                count_display,
                service,
                env_display,
                fmt_ts(last_seen),
                key=row[0],  # fingerprint as row key for detail lookup
            )

    def _update_stats(self) -> None:
        total, groups, sparkline_data = fetch_stats()

        self.query_one("#stats", Static).update(
            f"[dim]total events[/dim]\n"
            f"[bold #58a6ff]{total}[/bold #58a6ff]\n\n"
            f"[dim]unique groups[/dim]\n"
            f"[bold #58a6ff]{groups}[/bold #58a6ff]"
        )

        spark = self.query_one("#sparkline", Sparkline)
        spark.data = sparkline_data if sparkline_data else [0.0]

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        row = fetch_group_by_fingerprint(event.row_key.value)
        if row:
            self.push_screen(DetailModal(row))

    def action_cycle_env(self) -> None:
        envs = fetch_environments()
        if not envs:
            return
        # cycle: None → envs[0] → envs[1] → ... → None
        if self.env_filter is None:
            self.env_filter = envs[0]
        else:
            try:
                idx = envs.index(self.env_filter)
                self.env_filter = envs[idx + 1] if idx + 1 < len(envs) else None
            except ValueError:
                self.env_filter = None
        self.sub_title = self.env_filter if self.env_filter else "all environments"
        self.refresh_data()

    def on_key(self, event: events.Key) -> None:
        # prevent cursor wrapping — stop at top and bottom of the list
        table = self.query_one("#groups-table", DataTable)
        if event.key == "up" and table.cursor_row == 0:
            event.prevent_default()
        elif event.key == "down" and table.cursor_row >= table.row_count - 1:
            event.prevent_default()

    def action_manual_refresh(self) -> None:
        self.refresh_data()


if __name__ == "__main__":
    BeaconApp().run()
