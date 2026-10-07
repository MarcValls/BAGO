"""Run unchanged pytest collection, retaining each outcome before a suite hang.

Usage (from the backend being tested):
  python -B <this-file> <output-prefix> <pytest arguments...>

This observer does not select, skip, monkeypatch or time-limit individual tests.
Use an external whole-run timeout and pytest's faulthandler_timeout for hangs.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Same local backend import root as tests/conftest.py; usable on an isolated HEAD.
sys.path.insert(0, str(Path.cwd()))
import pytest


class Observer:
    def __init__(self, output):
        self.output = output

    def record(self, **values):
        values["at"] = datetime.now(timezone.utc).isoformat()
        self.output.write(json.dumps(values, ensure_ascii=True) + "\n")
        self.output.flush()

    def pytest_runtest_logstart(self, nodeid, location):
        self.record(event="start", nodeid=nodeid)

    def pytest_runtest_logreport(self, report):
        self.record(event="report", nodeid=report.nodeid, phase=report.when,
                    outcome=report.outcome, duration=report.duration,
                    traceback=report.longreprtext if report.failed else "")

    def pytest_sessionfinish(self, session, exitstatus):
        self.record(event="finish", exitstatus=int(exitstatus), collected=session.testscollected,
                    failed=session.testsfailed)


if __name__ == "__main__":
    prefix = Path(sys.argv[1]).resolve()
    with prefix.with_suffix(".jsonl").open("w", encoding="utf-8", newline="\n") as output:
        observer = Observer(output)
        observer.record(event="runtime", cwd=str(Path.cwd()), executable=sys.executable,
                        python=sys.version, arguments=sys.argv[2:])
        result = pytest.main(sys.argv[2:], plugins=[observer])
    raise SystemExit(result)
