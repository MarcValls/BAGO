from __future__ import annotations

import subprocess
import sys
import time

from cli_bridge import run_cli
from handlers_chat import _send_with_watchdog


class _Context:
    def __init__(self, manager) -> None:
        self.session_mgr = manager


def test_watchdog_renews_timeout_when_manager_reports_activity() -> None:
    class ActiveManager:
        def send(self, _message: str, *, activity_callback=None) -> str:
            for _ in range(4):
                time.sleep(0.04)
                activity_callback()
            return "ok"

    response, error, elapsed_ms = _send_with_watchdog(_Context(ActiveManager()), "hola", 0.07)

    assert response == "ok"
    assert error is None
    assert elapsed_ms >= 140


def test_watchdog_times_out_only_after_inactivity() -> None:
    class SilentManager:
        def send(self, _message: str) -> str:
            time.sleep(0.15)
            return "late"

    response, error, _elapsed_ms = _send_with_watchdog(_Context(SilentManager()), "hola", 0.04)

    assert response is None
    assert error is not None
    assert error["timed_out"] is True
    assert error["chat_timeout_mode"] == "inactivity"


def test_watchdog_keeps_cooperative_live_worker_running_without_token_events() -> None:
    class CooperativeManager:
        def send(self, _message: str, *, activity_callback=None) -> str:
            time.sleep(0.15)
            return "ok"

    response, error, elapsed_ms = _send_with_watchdog(_Context(CooperativeManager()), "hola", 0.04)

    assert response == "ok"
    assert error is None
    assert elapsed_ms >= 140


def test_cli_timeout_is_renewed_by_process_output(tmp_path) -> None:
    activity: list[float] = []
    script = (
        "import sys,time; "
        "[(sys.stderr.write(str(i)),sys.stderr.flush(),time.sleep(0.06)) for i in range(4)]; "
        "print('complete')"
    )

    output = run_cli(
        [sys.executable, "-u", "-c", script],
        tmp_path,
        timeout=0.1,
        on_activity=lambda: activity.append(time.monotonic()),
    )

    assert output.strip() == "complete"
    assert len(activity) >= 5


def test_cli_still_times_out_when_process_is_silent(tmp_path) -> None:
    activity: list[float] = []
    try:
        run_cli(
            [sys.executable, "-u", "-c", "import time; time.sleep(0.2)"],
            tmp_path,
            timeout=0.05,
            on_activity=lambda: activity.append(time.monotonic()),
        )
    except subprocess.TimeoutExpired:
        assert activity
    else:
        raise AssertionError("silent CLI must hit the inactivity timeout")


def test_cli_reports_liveness_after_first_real_output(tmp_path) -> None:
    activity: list[float] = []
    script = "import time; print('turn.started', flush=True); time.sleep(0.25); print('complete')"

    output = run_cli(
        [sys.executable, "-u", "-c", script],
        tmp_path,
        timeout=0.4,
        on_activity=lambda: activity.append(time.monotonic()),
    )

    assert output.splitlines() == ["turn.started", "complete"]
    assert len(activity) >= 2
