import sqlite3
from datetime import datetime

from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import DataTable, Footer, Header, Label, Sparkline, Static

from core.github import create_issue, close_issue, github_configured

DB_PATH = "beacon.db"


# ── DB helpers ────────────────────────────────────────────────────────────────
# each function opens its own connection so they are safe to call from any context

def _migrate_db():
    """Add any missing columns so the dashboard works against older databases."""
    try:
        conn = sqlite3.connect(DB_PATH)
        for sql in [
            "ALTER TABLE groups ADD COLUMN status TEXT DEFAULT 'active'",
            "ALTER TABLE groups ADD COLUMN resolved_at TEXT",
            "ALTER TABLE groups ADD COLUMN github_issue_url TEXT",
            "ALTER TABLE groups ADD COLUMN github_issue_number INTEGER",
        ]:
            try:
                conn.execute(sql)
                conn.commit()
            except sqlite3.OperationalError:
                pass  # column already exists
        conn.close()
    except sqlite3.OperationalError:
        pass  # db doesn't exist yet — server hasn't started


def fetch_groups(env_filter=None, show_resolved=False):
    try:
        conn = sqlite3.connect(DB_PATH)

        conditions = []
        params = []

        if env_filter:
            conditions.append("environment = ?")
            params.append(env_filter)

        if not show_resolved:
            conditions.append("(status IS NULL OR status != 'resolved')")

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        rows = conn.execute(f"""
            SELECT fingerprint, exception_type, normalize_message,
                   function_chain, count, first_seen, last_seen, service, environment,
                   COALESCE(status, 'active'), resolved_at
            FROM groups
            {where}
            ORDER BY count DESC
        """, params).fetchall()
        conn.close()
        return rows
    except sqlite3.OperationalError:
        return []


def fetch_group_by_fingerprint(fp):
    try:
        conn = sqlite3.connect(DB_PATH)
        row = conn.execute("""
            SELECT fingerprint, exception_type, normalize_message,
                   function_chain, count, first_seen, last_seen, service, environment,
                   COALESCE(status, 'active'), resolved_at,
                   github_issue_url, github_issue_number
            FROM groups WHERE fingerprint = ?
        """, (fp,)).fetchone()
        conn.close()
        return row
    except sqlite3.OperationalError:
        return None


def save_github_issue(fp, url, number):
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            "UPDATE groups SET github_issue_url = ?, github_issue_number = ? WHERE fingerprint = ?",
            (url, number, fp),
        )
        conn.commit()
        conn.close()
    except sqlite3.OperationalError:
        pass


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
        total_groups = conn.execute(
            "SELECT COUNT(*) FROM groups WHERE status IS NULL OR status IN ('active', 'regressed')"
        ).fetchone()[0]
        resolved_count = conn.execute(
            "SELECT COUNT(*) FROM groups WHERE status = 'resolved'"
        ).fetchone()[0]

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
        return total_events, total_groups, sparkline_data, resolved_count
    except sqlite3.OperationalError:
        return 0, 0, [], 0


def fetch_spiking_fingerprints():
    """
    Return the set of fingerprints that are currently spiking.
    Runs the same window comparison used in alerts.py so the dashboard
    stays in sync with what triggered a Slack alert.
    """
    try:
        conn = sqlite3.connect(DB_PATH)

        candidates = conn.execute("""
            SELECT DISTINCT fingerprint FROM events
            WHERE timestamp >= datetime('now', '-10 minutes')
        """).fetchall()

        spiking = set()

        for (fp,) in candidates:
            current = conn.execute("""
                SELECT COUNT(*) FROM events
                WHERE fingerprint = ?
                AND timestamp >= datetime('now', '-5 minutes')
            """, (fp,)).fetchone()[0]

            previous = conn.execute("""
                SELECT COUNT(*) FROM events
                WHERE fingerprint = ?
                AND timestamp >= datetime('now', '-10 minutes')
                AND timestamp < datetime('now', '-5 minutes')
            """, (fp,)).fetchone()[0]

            if current < 3:
                continue
            if previous == 0 and current >= 5:
                spiking.add(fp)
            elif previous > 0 and (current / previous) >= 5:
                spiking.add(fp)

        conn.close()
        return spiking

    except sqlite3.OperationalError:
        return set()


def resolve_group(fp):
    """Mark a group as resolved. Any future occurrence will trigger a regression alert."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            "UPDATE groups SET status = 'resolved', resolved_at = datetime('now') WHERE fingerprint = ?",
            (fp,)
        )
        conn.commit()
        conn.close()
    except sqlite3.OperationalError:
        pass


def fmt_ts(ts):
    if not ts:
        return ""
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
        fp, exc_type, norm_msg, fn_chain, count, first_seen, last_seen, service, environment, status, resolved_at, github_issue_url, github_issue_number = self.row

        chain_lines = "\n  ".join(fn_chain.split("->"))
        env_color = "red" if environment == "production" else "yellow"

        widgets = [Label(f"[bold red]{exc_type}[/bold red]", id="modal-title")]

        if status == 'regressed':
            widgets.append(Label("[bold #ff9a3c]↩ regressed — came back after being resolved[/bold #ff9a3c]"))
        elif status == 'resolved':
            resolved_str = f"  ({fmt_ts(resolved_at)})" if resolved_at else ""
            widgets.append(Label(f"[dim]✓ resolved{resolved_str}[/dim]"))

        widgets.extend([
            Static(""),
            Label(f"[dim]service[/dim]     {service}   [dim]env[/dim]  [{env_color}]{environment}[/{env_color}]"),
            Static(""),
            Label("[dim]message[/dim]"),
            Label(f"  {norm_msg}"),
            Static(""),
            Label("[dim]call chain[/dim]"),
            Label(f"  {chain_lines}"),
            Static(""),
            Label(f"[dim]count[/dim]       [yellow]{count}[/yellow]"),
            Label(f"[dim]first seen[/dim]  [green]{fmt_ts(first_seen)}[/green]"),
            Label(f"[dim]last seen[/dim]   [green]{fmt_ts(last_seen)}[/green]"),
            Static(""),
            Label(f"[dim]{fp}[/dim]"),
        ])

        if github_issue_url:
            widgets.extend([
                Static(""),
                Label(f"[dim]github[/dim]      [link={github_issue_url}][#58a6ff]#{github_issue_number} ↗[/#58a6ff][/link]"),
            ])

        widgets.extend([
            Static(""),
            Label("[dim]g  github issue   x  resolve   ESC  close[/dim]"),
        ])

        yield Vertical(*widgets, id="modal-box")


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
        Binding("x", "resolve_group", "Resolve"),
        Binding("h", "toggle_resolved", "History"),
        Binding("g", "open_github", "GitHub Issue"),
    ]

    TITLE = "beacon"
    SUB_TITLE = "all environments"

    env_filter: str | None = None
    show_resolved: bool = False

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
        _migrate_db()

        table = self.query_one("#groups-table", DataTable)
        table.cursor_type = "row"
        table.add_columns("#", "exception", "message", "count", "service", "env", "last seen")

        self.refresh_data()
        self.set_interval(2, self.refresh_data)

    def refresh_data(self) -> None:
        self._update_table()
        self._update_stats()

    def _update_table(self) -> None:
        table = self.query_one("#groups-table", DataTable)
        table.clear()

        spiking = fetch_spiking_fingerprints()

        for i, row in enumerate(fetch_groups(self.env_filter, self.show_resolved), start=1):
            fp, exc_type, norm_msg, _, count, _, last_seen, service, environment, status, _ = row

            short_msg = norm_msg[:30] + "…" if len(norm_msg) > 30 else norm_msg

            # row number — orange for regressions, dim for resolved
            if status == 'regressed':
                row_num = f"[bold #ff9a3c]{i}[/bold #ff9a3c]"
            elif status == 'resolved':
                row_num = f"[dim]{i}[/dim]"
            else:
                row_num = str(i)

            # exception type — prefix with regression indicator
            if status == 'regressed':
                exc_display = f"[bold #ff9a3c]↩ {exc_type}[/bold #ff9a3c]"
            elif status == 'resolved':
                exc_display = f"[dim]{exc_type}[/dim]"
            elif fp in spiking:
                exc_display = f"[bold red]{exc_type}[/bold red]"
            else:
                exc_display = f"[red]{exc_type}[/red]"

            # count — spike takes priority, then severity colouring
            if fp in spiking and status != 'resolved':
                count_display = f"[bold red]↑ {count}[/bold red]"
            elif status == 'resolved':
                count_display = f"[dim]{count}[/dim]"
            elif count >= 50:
                count_display = f"[bold red]{count}[/bold red]"
            elif count >= 10:
                count_display = f"[yellow]{count}[/yellow]"
            else:
                count_display = str(count)

            env_display = (
                f"[red]{environment}[/red]"
                if environment == "production"
                else f"[yellow]{environment}[/yellow]"
            )
            if status == 'resolved':
                env_display = f"[dim]{environment}[/dim]"

            table.add_row(
                row_num,
                exc_display,
                short_msg,
                count_display,
                service,
                env_display,
                fmt_ts(last_seen),
                key=fp,
            )

    def _update_stats(self) -> None:
        total, groups, sparkline_data, resolved = fetch_stats()

        stats_text = (
            f"[dim]total events[/dim]\n"
            f"[bold #58a6ff]{total}[/bold #58a6ff]\n\n"
            f"[dim]active groups[/dim]\n"
            f"[bold #58a6ff]{groups}[/bold #58a6ff]"
        )
        if resolved > 0:
            stats_text += (
                f"\n\n[dim]resolved[/dim]\n"
                f"[dim #58a6ff]{resolved}[/dim #58a6ff]  [dim](h to view)[/dim]"
            )

        self.query_one("#stats", Static).update(stats_text)

        spark = self.query_one("#sparkline", Sparkline)
        spark.data = sparkline_data if sparkline_data else [0.0]

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        row = fetch_group_by_fingerprint(event.row_key.value)
        if row:
            self.push_screen(DetailModal(row))

    def action_resolve_group(self) -> None:
        table = self.query_one("#groups-table", DataTable)
        if table.row_count == 0:
            return
        row_keys = list(table.rows.keys())
        if table.cursor_row >= len(row_keys):
            return
        fp = row_keys[table.cursor_row].value

        # capture github info before resolving
        row = fetch_group_by_fingerprint(fp)
        issue_number = row[12] if row else None

        resolve_group(fp)

        if issue_number:
            try:
                close_issue(issue_number)
                self.notify(f"Resolved and closed GitHub issue #{issue_number}.")
            except Exception:
                self.notify("Resolved. (Could not close GitHub issue — check GITHUB_TOKEN.)")
        else:
            self.notify("Resolved. You'll be alerted immediately if it comes back.")

        self.refresh_data()

    def action_open_github(self) -> None:
        table = self.query_one("#groups-table", DataTable)
        if table.row_count == 0:
            return
        row_keys = list(table.rows.keys())
        if table.cursor_row >= len(row_keys):
            return
        fp = row_keys[table.cursor_row].value

        row = fetch_group_by_fingerprint(fp)
        if not row:
            return

        fp, exc_type, norm_msg, fn_chain, count, first_seen, last_seen, service, environment, _, _, github_issue_url, _ = row

        if github_issue_url:
            self.notify(f"Already linked: {github_issue_url}")
            return

        if not github_configured():
            self.notify("Set GITHUB_TOKEN and GITHUB_REPO to enable GitHub issues.", severity="error")
            return

        try:
            number, url = create_issue(
                fp, exc_type, norm_msg, fn_chain, count, first_seen, last_seen, service, environment
            )
            save_github_issue(fp, url, number)
            self.notify(f"GitHub issue #{number} created.")
        except Exception as e:
            self.notify(f"GitHub error: {e}", severity="error")
            return

        self.refresh_data()

    def action_toggle_resolved(self) -> None:
        self.show_resolved = not self.show_resolved
        label = "showing resolved groups" if self.show_resolved else "hiding resolved groups"
        self.notify(label)
        self.refresh_data()

    def action_cycle_env(self) -> None:
        envs = fetch_environments()
        if not envs:
            return
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
