import sqlite3
from datetime import datetime

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import DataTable, Footer, Header, Label, Sparkline, Static

DB_PATH = "errscope.db"


# ── DB helpers ────────────────────────────────────────────────────────────────
# each function opens its own connection so they are safe to call from any context

def fetch_groups():
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("""
        SELECT fingerprint, exception_type, normalize_message,
               function_chain, count, first_seen, last_seen
        FROM groups
        ORDER BY count DESC
    """).fetchall()
    conn.close()
    return rows


def fetch_stats():
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
        fp, exc_type, norm_msg, fn_chain, count, first_seen, last_seen = self.row

        # each step in the call chain gets its own line for readability
        chain_lines = "\n  ".join(fn_chain.split("->"))

        yield Vertical(
            Label(f"[bold red]{exc_type}[/bold red]", id="modal-title"),
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

class ErrScopeApp(App):

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
    ]

    TITLE = "errscope"
    SUB_TITLE = "live error monitoring"

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
        table.add_columns("#", "exception", "message", "count", "last seen")

        # initial load then refresh every 2 seconds
        self.refresh_data()
        self.set_interval(2, self.refresh_data)

    def refresh_data(self) -> None:
        self._update_table()
        self._update_stats()

    def _update_table(self) -> None:
        table = self.query_one("#groups-table", DataTable)
        table.clear()

        for i, row in enumerate(fetch_groups(), start=1):
            _, exc_type, norm_msg, _, count, _, last_seen = row

            short_msg = norm_msg[:42] + "…" if len(norm_msg) > 42 else norm_msg

            # colour count by severity: red when high, yellow when moderate
            if count >= 50:
                count_display = f"[bold red]{count}[/bold red]"
            elif count >= 10:
                count_display = f"[yellow]{count}[/yellow]"
            else:
                count_display = str(count)

            table.add_row(
                str(i),
                f"[red]{exc_type}[/red]",
                short_msg,
                count_display,
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
        # find the full row data by fingerprint and open the detail modal
        for row in fetch_groups():
            if row[0] == event.row_key.value:
                self.push_screen(DetailModal(row))
                break

    def action_manual_refresh(self) -> None:
        self.refresh_data()


if __name__ == "__main__":
    ErrScopeApp().run()
