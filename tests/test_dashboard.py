import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

pytest.importorskip("flask")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "laptop_app" / "dashboard"))

import app as dashboard  # noqa: E402
from storage import init_db, insert_reading  # noqa: E402


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


@pytest.fixture(autouse=True)
def isolate_dashboard_data(tmp_path, monkeypatch):
    monkeypatch.setattr(dashboard, "_poller_started", True)
    monkeypatch.setattr(dashboard, "DB_PATH", tmp_path / "readings.sqlite3")
    monkeypatch.setattr(dashboard, "LOG_PATH", tmp_path / "app.log")
    monkeypatch.setattr(dashboard, "metadata", {"capture_date": "2026-11-17", "solar_angle": 0.0})
    init_db(dashboard.DB_PATH)
    yield


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


def test_metadata_then_readings_are_tagged():
    client = dashboard.app.test_client()
    response = client.post("/api/metadata", json={"capture_date": "2026-11-17", "solar_angle": 25})
    assert response.status_code == 200
    insert_reading(dashboard.DB_PATH, 1.0, "2026-11-17", 25.0, 4.5, 0.1, 0.45)
    rows = client.get("/api/readings?day=2026-11-17").get_json()
    assert rows[0]["solar_angle"] == 25.0


def test_days_and_csv_export():
    insert_reading(dashboard.DB_PATH, 1.0, "2026-11-17", 25.0, 4.5, 0.1, 0.45)
    client = dashboard.app.test_client()
    assert client.get("/api/days").get_json() == ["2026-11-17"]
    csv_response = client.get("/export.csv?day=2026-11-17")
    assert csv_response.status_code == 200
    assert b"capture_date" in csv_response.data
    assert b"solar_angle" in csv_response.data
    assert "solarlab_2026-11-17.csv" in csv_response.headers["Content-Disposition"]


def test_logs_route_returns_list():
    dashboard.LOG_PATH.write_text("2026-11-17 INFO hello\n", encoding="utf-8")
    client = dashboard.app.test_client()
    assert "hello" in client.get("/api/logs").get_json()[0]
