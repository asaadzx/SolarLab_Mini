import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

pytest.importorskip("flask")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "laptop_app" / "dashboard"))

import app as dashboard  # noqa: E402


class StubHandler(BaseHTTPRequestHandler):
    PAYLOAD = {"voltage": 4.536, "current": 0.125, "power": 0.567, "timestamp": 1234}

    def do_GET(self):
        body = json.dumps(self.PAYLOAD).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


@pytest.fixture
def stub_server(monkeypatch):
    server = ThreadingHTTPServer(("127.0.0.1", 0), StubHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address[:2]
    monkeypatch.setattr(dashboard, "ESP_URL", "http://{}:{}/data".format(host, port))
    yield
    server.shutdown()
    server.server_close()
    thread.join(timeout=2)


def test_index_renders(stub_server):
    response = dashboard.app.test_client().get("/")
    assert response.status_code == 200
    assert b"SolarLab Mini" in response.data


def test_api_latest_proxies_json(stub_server):
    response = dashboard.app.test_client().get("/api/latest")
    assert response.status_code == 200
    assert response.get_json() == StubHandler.PAYLOAD


def test_api_latest_reports_connection_error(monkeypatch):
    monkeypatch.setattr(dashboard, "ESP_URL", "http://127.0.0.1:1/data")
    response = dashboard.app.test_client().get("/api/latest")
    assert response.status_code == 200
    assert "error" in response.get_json()
