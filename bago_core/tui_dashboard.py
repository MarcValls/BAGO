#!/usr/bin/env python3
"""BAGO TUI Dashboard — Fase 2: TUI Minimalista (textual).

Entry point:
    python -m bago_core.tui_dashboard [--base-path PATH]

Layout (3-column dashboard):
┌─ BAGO Session ─────────────────────────┐
│ Provider: …  Model: …  Mode: …         │
├─────────────┬─────────────┬────────────┤
│ NODOS       │ CONEXIONES  │ ACCIONES   │
│             │             │            │
│             │             │            │
└─────────────┴─────────────┴────────────┘
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

# Ensure bago_core is on path when run standalone
_BAGO_ROOT = Path(__file__).resolve().parents[1]
if str(_BAGO_ROOT) not in sys.path:
    sys.path.insert(0, str(_BAGO_ROOT))

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import DataTable, Footer, Header, Static, Label, Rule

from bago_core import session_control
from bago_core.node_control_state import status as node_status
from bago_core.node_control_store import registry_paths


class SessionHeader(Static):
    """Top bar showing active session metadata."""

    def __init__(self, base_path: Path) -> None:
        self.base_path = base_path
        super().__init__()

    def on_mount(self) -> None:
        sessions = session_control.list_sessions(self.base_path)
        if sessions:
            s = sessions[0]
            text = (
                f"Session: {s.get('sid','—')[:8]}…  |  "
                f"Provider: {s.get('provider','—')}  |  "
                f"Model: {s.get('model','—')}  |  "
                f"Mode: {s.get('bago_mode','B')}  |  "
                f"Agent: {s.get('active_agent','default')}  |  "
                f"Calls: {s.get('total_calls',0)}  Tokens: {s.get('total_tokens',0)}"
            )
        else:
            text = "No active sessions — run `bago session create`"
        self.update(text)


class NodesPanel(Static):
    """Left panel: installations + pieces."""

    DEFAULT_CSS = """
    NodesPanel { height: 100%; border: solid green; }
    """

    def __init__(self, base_path: Path) -> None:
        self.base_path = base_path
        super().__init__()

    def compose(self) -> ComposeResult:
        yield Label("[bold]NODOS[/bold]")
        yield Rule()
        yield DataTable(id="nodes_table")

    def on_mount(self) -> None:
        table = self.query_one("#nodes_table", DataTable)
        table.add_columns("Name", "Type", "Scope", "Status")
        try:
            st = node_status(self.base_path)
            for inst in st.get("installations_data", []):
                table.add_row(inst.get("name", "—"), "installation", inst.get("scope", "—"), "✓")
            for piece in st.get("pieces_data", []):
                table.add_row(piece.get("name", "—"), piece.get("type", "—"), piece.get("scope", "—"), "✓")
        except Exception as exc:
            table.add_row("Error", str(exc), "", "")


class ConnectionsPanel(Static):
    """Middle panel: connectors matrix."""

    DEFAULT_CSS = """
    ConnectionsPanel { height: 100%; border: solid cyan; }
    """

    def __init__(self, base_path: Path) -> None:
        self.base_path = base_path
        super().__init__()

    def compose(self) -> ComposeResult:
        yield Label("[bold]CONEXIONES[/bold]")
        yield Rule()
        yield DataTable(id="conn_table")

    def on_mount(self) -> None:
        table = self.query_one("#conn_table", DataTable)
        table.add_columns("From → To", "Mode", "Status")
        try:
            st = node_status(self.base_path)
            for c in st.get("connectors_data", []):
                label = f"{c.get('installation','—')} → {c.get('piece','—')}"
                table.add_row(label, c.get("mode", "—"), "✓")
            if not st.get("connectors_data"):
                table.add_row("No connectors", "", "")
        except Exception as exc:
            table.add_row("Error", str(exc), "")


class ActionsPanel(Static):
    """Right panel: recent evidence / actions."""

    DEFAULT_CSS = """
    ActionsPanel { height: 100%; border: solid magenta; }
    """

    def __init__(self, base_path: Path) -> None:
        self.base_path = base_path
        super().__init__()

    def compose(self) -> ComposeResult:
        yield Label("[bold]ÚLTIMAS ACCIONES[/bold]")
        yield Rule()
        yield DataTable(id="actions_table")

    def on_mount(self) -> None:
        table = self.query_one("#actions_table", DataTable)
        table.add_columns("Time", "Action", "Target", "Result")
        try:
            paths = registry_paths(self.base_path)
            ev_path = paths.evidence
            rows: list[dict[str, Any]] = []
            if ev_path.exists():
                with ev_path.open("r", encoding="utf-8") as fh:
                    for line in fh:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            rows.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
            # Show last 15
            for row in rows[-15:][::-1]:
                ts = row.get("timestamp", "—")[11:19]  # HH:MM:SS
                action = row.get("action", "—")
                target = row.get("target", {}).get("name", "—")
                result = row.get("result", "—")
                table.add_row(ts, action, target, result)
            if not rows:
                table.add_row("—", "No actions yet", "", "")
        except Exception as exc:
            table.add_row("—", f"Error: {exc}", "", "")


class BagoDashboardApp(App[None]):
    """Textual TUI for BAGO Phase-2 dashboard."""

    CSS = """
    Screen { align: center middle; }
    .dashboard { width: 100%; height: 100%; }
    SessionHeader { height: 3; content-align: center middle; background: $surface; color: $text; }
    """

    BINDINGS = [
        ("q", "quit", "Salir"),
        ("r", "refresh", "Refrescar"),
    ]

    def __init__(self, base_path: Path) -> None:
        self.base_path = base_path
        super().__init__()

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield SessionHeader(self.base_path)
        with Horizontal(classes="dashboard"):
            yield NodesPanel(self.base_path)
            yield ConnectionsPanel(self.base_path)
            yield ActionsPanel(self.base_path)
        yield Footer()

    def action_refresh(self) -> None:
        self.refresh(recompose=True)


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="BAGO TUI Dashboard")
    parser.add_argument("--base-path", default=".", type=Path)
    args = parser.parse_args(argv)
    app = BagoDashboardApp(base_path=args.base_path.expanduser().resolve())
    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
