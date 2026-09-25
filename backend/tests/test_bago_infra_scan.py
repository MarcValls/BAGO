from __future__ import annotations

import http.server
import json
import sys
import threading
from pathlib import Path

import pytest

TOOLS_DIR = Path(__file__).resolve().parents[1] / ".bago" / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import bago_infra_scan as infra_scan


class _OllamaHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/":
            body = b"Ollama is running"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
        elif self.path == "/api/version":
            body = b'{"version":"0.4.0"}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
        elif self.path == "/api/tags":
            body = b'{"models":[{"name":"llama3"},{"name":"mistral"}]}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
        else:
            body = b"{}"
            self.send_response(404)
            self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, _format: str, *_args: object) -> None:
        return


@pytest.fixture
def ollama_server():
    server = http.server.HTTPServer(("127.0.0.1", 0), _OllamaHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield int(server.server_address[1])
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_infra_scan_identifies_local_ollama_and_extracts_models(ollama_server: int) -> None:
    assert infra_scan._port_open("127.0.0.1", ollama_server)
    assert infra_scan._probe_http("127.0.0.1", 1, "/") is None

    service = infra_scan._identify_service("127.0.0.1", ollama_server)

    assert service["name"] == "ollama"
    assert service["version"] == "0.4.0"
    assert service["models"] == ["llama3", "mistral"]
    assert infra_scan._extract_models('{"models":[{"name":"alpha"},{"id":"beta"}]}') == ["alpha", "beta"]


def test_infra_scan_report_and_state_save(tmp_path: Path, monkeypatch, ollama_server: int) -> None:
    monkeypatch.setattr(infra_scan, "_netstat_ports", lambda: [ollama_server])

    services = infra_scan.scan(quick=False)
    payload = infra_scan.build_payload(tmp_path, services, quick=False, host="127.0.0.1")
    state_path = infra_scan.save_payload(tmp_path, payload)

    assert len(services) == 1
    assert services[0]["name"] == "ollama"
    assert json.loads(state_path.read_text(encoding="utf-8"))["services"] == services
    assert "Services found: 1" in infra_scan.format_report(payload)


def test_infra_scan_runtime_has_no_embedded_test_switch() -> None:
    with pytest.raises(SystemExit) as exc:
        infra_scan.main(["--test"])
    assert exc.value.code == 2
