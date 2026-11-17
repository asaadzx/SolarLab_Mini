# Dashboard Data and Storage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the Flask dashboard into a continuously logging app with SQLite storage, metadata tagging, three charts, day-based CSV export, and visible error logs.

**Architecture:** Add focused `storage.py` and `poller.py` modules beside the existing `app.py`, keep the Flask routes thin, and update the template/CSS for the new controls. Python standard library handles SQLite, CSV, logging, and threading; no new runtime dependencies.

**Tech Stack:** Python 3.14, Flask, requests, sqlite3, threading, logging, Chart.js (CDN already in use), pytest.

## Global Constraints

- No new third-party runtime dependencies.
- ESP32 JSON schema stays `voltage`, `current`, `power`, `timestamp` at `http://192.168.4.1/data`.
- Keep `/api/latest` live-proxy behavior and the existing 30 tests passing.
- SQLite default path: `laptop_app/dashboard/data/solarlab.sqlite3`.
- Log default path: `laptop_app/dashboard/data/app.log` (rotating).
- Comments are required on every new function and variable.
- Docker packaging is phase 2 and out of scope for this plan.
- Final commits are pushed to `origin/master`.

---

### Task 1: SQLite storage and CSV export module

**Files:**
- Create: `laptop_app/dashboard/storage.py`
- Create: `tests/test_dashboard_storage.py`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `CSV_HEADER`, `init_db(db_path)`, `insert_reading(db_path, recorded_at, capture_date, solar_angle, voltage, current, power)`, `get_readings(db_path, capture_date) -> list[dict]`, `get_days(db_path) -> list[str]`, `export_day_csv(db_path, capture_date) -> str`.

- [ ] **Step 1: Write the failing tests**

```python
import csv
import io
from pathlib import Path

from storage import CSV_HEADER, export_day_csv, get_days, get_readings, init_db, insert_reading


def test_init_db_creates_table(tmp_path):
    db_path = tmp_path / "nested" / "readings.sqlite3"
    init_db(db_path)
    assert db_path.exists() is True
    assert get_readings(db_path, "2026-11-17") == []


def test_insert_and_query_by_day(tmp_path):
    db_path = tmp_path / "readings.sqlite3"
    init_db(db_path)
    insert_reading(db_path, 100.0, "2026-11-17", 15.0, 4.5, 0.1, 0.45)
    insert_reading(db_path, 101.0, "2026-11-18", 30.0, 4.6, 0.2, 0.92)
    rows = get_readings(db_path, "2026-11-17")
    assert len(rows) == 1
    assert rows[0]["solar_angle"] == 15.0
    assert get_days(db_path) == ["2026-11-18", "2026-11-17"]


def test_export_day_csv_contains_metadata(tmp_path):
    db_path = tmp_path / "readings.sqlite3"
    init_db(db_path)
    insert_reading(db_path, 100.0, "2026-11-17", 15.0, 4.5, 0.1, 0.45)
    text = export_day_csv(db_path, "2026-11-17")
    rows = list(csv.DictReader(io.StringIO(text)))
    assert rows[0]["capture_date"] == "2026-11-17"
    assert rows[0]["solar_angle"] == "15.0"
    assert list(rows[0].keys()) == CSV_HEADER
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_dashboard_storage.py -q`
Expected: FAIL with "No module named 'storage'".

- [ ] **Step 3: Create `laptop_app/dashboard/storage.py`**

```python
"""SQLite storage and CSV export for SolarLab Mini dashboard readings."""

import csv  # Build CSV text from stored rows
import io  # In-memory text buffer for CSV output
import sqlite3  # Standard-library SQL database
from pathlib import Path  # Filesystem paths for the database file

CSV_HEADER = [  # Column order used by both the table and CSV export
    "recorded_at",  # Unix timestamp when the reading was polled
    "capture_date",  # Manual capture day entered in the dashboard (YYYY-MM-DD)
    "solar_angle",  # Manual solar panel angle in degrees
    "voltage",  # Bus voltage in volts from the INA219
    "current",  # Current in amps from the INA219
    "power",  # Power in watts from the INA219
]


def connect(db_path):
    """Open a SQLite connection, creating the parent folder if needed."""
    db_path = Path(db_path)  # Accept both str and Path inputs
    db_path.parent.mkdir(parents=True, exist_ok=True)  # Ensure the data folder exists
    return sqlite3.connect(str(db_path), timeout=5)  # connection with a 5s lock timeout


def init_db(db_path):
    """Create the readings table and its date index if they do not exist."""
    connection = connect(db_path)  # Open the database file
    try:
        connection.execute(  # SQL creates the table only on first run
            "CREATE TABLE IF NOT EXISTS readings ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "recorded_at REAL NOT NULL, "
            "capture_date TEXT NOT NULL, "
            "solar_angle REAL NOT NULL, "
            "voltage REAL, "
            "current REAL, "
            "power REAL)"
        )
        connection.execute(  # Index makes day lookups fast as data grows
            "CREATE INDEX IF NOT EXISTS idx_readings_capture_date "
            "ON readings(capture_date)"
        )
        connection.commit()  # Persist the schema changes
    finally:
        connection.close()  # Always release the database file


def insert_reading(db_path, recorded_at, capture_date, solar_angle, voltage, current, power):
    """Append one reading, tagged with the current capture day and solar angle."""
    connection = connect(db_path)  # Open the database file
    try:
        connection.execute(  # Insert one row with six values
            "INSERT INTO readings "
            "(recorded_at, capture_date, solar_angle, voltage, current, power) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (recorded_at, capture_date, solar_angle, voltage, current, power),
        )
        connection.commit()  # Persist the new reading
    finally:
        connection.close()  # Always release the database file


def get_readings(db_path, capture_date):
    """Return all readings for one capture day as a list of dictionaries."""
    connection = connect(db_path)  # Open the database file
    try:
        rows = connection.execute(  # Query only the selected day, oldest first
            "SELECT recorded_at, capture_date, solar_angle, voltage, current, power "
            "FROM readings WHERE capture_date = ? ORDER BY recorded_at",
            (capture_date,),  # Parameter prevents SQL injection
        ).fetchall()  # Materialize all matching rows
    finally:
        connection.close()  # Always release the database file
    return [dict(zip(CSV_HEADER, row)) for row in rows]  # Convert rows to dicts


def get_days(db_path):
    """Return distinct capture dates, newest first, for the day picker."""
    connection = connect(db_path)  # Open the database file
    try:
        rows = connection.execute(  # DISTINCT removes duplicate day values
            "SELECT DISTINCT capture_date FROM readings ORDER BY capture_date DESC"
        ).fetchall()  # Materialize the dates
    finally:
        connection.close()  # Always release the database file
    return [row[0] for row in rows]  # Flatten each one-element row


def export_day_csv(db_path, capture_date):
    """Return CSV text for one day, including the metadata columns."""
    rows = get_readings(db_path, capture_date)  # Reuse the day query
    buffer = io.StringIO()  # In-memory destination for CSV text
    writer = csv.DictWriter(buffer, fieldnames=CSV_HEADER)  # Writes named columns
    writer.writeheader()  # First line is the column names
    writer.writerows(rows)  # One line per stored reading
    return buffer.getvalue()  # Complete CSV document as a string
```

- [ ] **Step 4: Ignore generated dashboard data**

Append this line to `.gitignore`:

```gitignore
# Generated dashboard data
laptop_app/dashboard/data/
```

- [ ] **Step 5: Add path setup to the storage test and run it**

Insert these lines at the top of `tests/test_dashboard_storage.py` before the `from storage import ...` line:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "laptop_app" / "dashboard"))
```

Run: `python -m pytest tests/test_dashboard_storage.py -q`
Expected: PASS (3 tests).

- [ ] **Step 6: Commit**

```bash
git add laptop_app/dashboard/storage.py tests/test_dashboard_storage.py .gitignore
git commit -m "feat: add SQLite reading storage and CSV export"
```

---

### Task 2: Background poller with logging

**Files:**
- Create: `laptop_app/dashboard/poller.py`
- Create: `tests/test_dashboard_poller.py`

**Interfaces:**
- Consumes: `insert_reading` from `laptop_app/dashboard/storage.py`.
- Produces: `poll_once(esp_url, db_path, metadata, timeout=2)`, `start_poller(esp_url, db_path, get_metadata, stop_event, interval=1.0, logger=None) -> threading.Thread`.

- [ ] **Step 1: Write the failing tests**

```python
import json
import logging
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "laptop_app" / "dashboard"))

from poller import poll_once, start_poller  # noqa: E402
from storage import get_readings, init_db  # noqa: E402


class StubHandler(BaseHTTPRequestHandler):
    PAYLOAD = {"voltage": 4.5, "current": 0.1, "power": 0.45, "timestamp": 100}

    def do_GET(self):
        body = json.dumps(self.PAYLOAD).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def test_poll_once_stores_tagged_reading(tmp_path):
    server = ThreadingHTTPServer(("127.0.0.1", 0), StubHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address[:2]
    db_path = tmp_path / "readings.sqlite3"
    init_db(db_path)
    metadata = {"capture_date": "2026-11-17", "solar_angle": 25.0}
    poll_once("http://{}:{}/data".format(host, port), db_path, metadata)
    rows = get_readings(db_path, "2026-11-17")
    assert len(rows) == 1
    assert rows[0]["solar_angle"] == 25.0
    assert rows[0]["voltage"] == 4.5
    server.shutdown()
    server.server_close()
    thread.join(timeout=2)


def test_start_poller_logs_failure_and_stops(tmp_path):
    db_path = tmp_path / "readings.sqlite3"
    init_db(db_path)
    stop_event = threading.Event()
    metadata = {"capture_date": "2026-11-17", "solar_angle": 0.0}
    records = []

    class Capture(logging.Handler):
        def emit(self, record):
            records.append(record.getMessage())
            stop_event.set()  # The first failed poll ends the loop

    logger = logging.getLogger("test-poller")
    logger.addHandler(Capture())
    logger.setLevel(logging.INFO)
    worker = start_poller(
        "http://127.0.0.1:1/data", db_path, lambda: metadata,
        stop_event, interval=0.01, logger=logger,
    )
    worker.join(timeout=2)
    assert worker.is_alive() is False
    assert any("poll failed" in line for line in records)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_dashboard_poller.py -q`
Expected: FAIL with "No module named 'poller'".

- [ ] **Step 3: Create `laptop_app/dashboard/poller.py`**

```python
"""Background poller that saves ESP32 readings and logs problems."""

import logging  # Standard logging module for events and errors
import threading  # Background thread support
import time  # Unix timestamps for stored readings
from pathlib import Path  # Path normalization

import requests  # HTTP client for the ESP32 endpoint

from storage import insert_reading  # Database insert helper


def poll_once(esp_url, db_path, metadata, timeout=2):
    """Fetch one ESP32 reading and store it with the current metadata tags."""
    response = requests.get(esp_url, timeout=timeout)  # GET /data from the board
    reading = response.json()  # Parse the JSON payload
    insert_reading(  # Append the tagged reading to SQLite
        Path(db_path),  # Database file path
        time.time(),  # Recorded-at timestamp
        metadata["capture_date"],  # Manual capture day
        metadata["solar_angle"],  # Manual solar angle
        reading.get("voltage"),  # Voltage from the sensor
        reading.get("current"),  # Current from the sensor
        reading.get("power"),  # Power from the sensor
    )
    return reading  # Return the parsed payload for logging/tests


def _run(esp_url, db_path, get_metadata, stop_event, interval, logger):
    """Poll until stop_event is set; never let an error kill the thread."""
    while not stop_event.is_set():  # Loop while the app is running
        try:
            metadata = get_metadata()  # Read the latest date/angle under lock
            reading = poll_once(esp_url, db_path, metadata)  # Fetch and store one row
            logger.info("logged reading: %s", reading)  # Success event
        except Exception as e:  # Network, JSON, or database failure
            logger.error("poll failed: %s", e)  # Log the problem and continue
        stop_event.wait(interval)  # Sleep, but wake immediately on stop


def start_poller(esp_url, db_path, get_metadata, stop_event, interval=1.0, logger=None):
    """Start and return a daemon thread that logs readings every interval."""
    active_logger = logger or logging.getLogger(__name__)  # Logger supplied by caller
    worker = threading.Thread(  # Thread object for the background loop
        target=_run,  # Function the thread runs
        args=(esp_url, db_path, get_metadata, stop_event, interval, active_logger),  # Arguments
        daemon=True,  # Do not block process exit
        name="solarlab-poller",  # Helpful name in logs/debuggers
    )
    worker.start()  # Begin polling
    return worker  # Caller may keep the thread for tests/shutdown
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_dashboard_poller.py -q`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add laptop_app/dashboard/poller.py tests/test_dashboard_poller.py
git commit -m "feat: add background reading poller with error logging"
```

---

### Task 3: Flask routes, metadata, and app logging

**Files:**
- Modify: `laptop_app/dashboard/app.py`
- Modify: `tests/test_dashboard.py`

**Interfaces:**
- Consumes: `get_readings`, `get_days`, `export_day_csv` from Task 1; `start_poller` from Task 2.
- Produces: routes `/`, `/api/latest`, `/api/readings`, `/api/days`, `/api/metadata` (POST), `/api/logs`, `/export.csv`; module globals `ESP_URL`, `DB_PATH`, `LOG_PATH`, `metadata`, `logger`.

- [ ] **Step 1: Replace `laptop_app/dashboard/app.py`**

```python
"""Flask dashboard with stored readings, metadata, CSV export, and logs."""

import logging  # Application event/error logging
import threading  # Protect shared metadata and poller startup
from datetime import date  # Default capture day
from logging.handlers import RotatingFileHandler  # Rotating log file
from pathlib import Path  # Filesystem paths

from flask import Flask, Response, jsonify, render_template, request  # Web framework
import requests  # Live proxy to the ESP32

from poller import start_poller  # Background logger thread
from storage import export_day_csv, get_days, get_readings, init_db  # Database helpers

ESP_URL = "http://192.168.4.1/data"  # ESP32 JSON endpoint
BASE_DIR = Path(__file__).resolve().parent  # Folder containing this app
DATA_DIR = BASE_DIR / "data"  # Folder for DB and log files
DB_PATH = DATA_DIR / "solarlab.sqlite3"  # SQLite database file
LOG_PATH = DATA_DIR / "app.log"  # Rotating application log file

app = Flask(__name__)  # Flask application object
DATA_DIR.mkdir(parents=True, exist_ok=True)  # Create data folder on startup
metadata = {"capture_date": date.today().isoformat(), "solar_angle": 0.0}  # Current tags
metadata_lock = threading.Lock()  # Guards metadata reads/writes
_poller_started = False  # Prevents duplicate poller threads
_poller_lock = threading.Lock()  # Guards poller startup
stop_event = threading.Event()  # Signals the poller to stop

logger = logging.getLogger("solarlab.dashboard")  # Named application logger
logger.setLevel(logging.INFO)  # Record info and above
if not logger.handlers:  # Configure file logging only once
    handler = RotatingFileHandler(  # Keeps logs bounded in size
        str(LOG_PATH), maxBytes=1_000_000, backupCount=3  # 1 MB x 4 files
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)  # Attach the rotating file handler

init_db(DB_PATH)  # Ensure the table exists before any request


def get_metadata():
    """Return a safe copy of the current capture date and solar angle."""
    with metadata_lock:  # Hold the lock while copying
        return dict(metadata)  # Copy avoids callers mutating shared state


def ensure_poller():
    """Start the background logger once, on the first browser request."""
    global _poller_started  # Module-level startup flag
    with _poller_lock:  # Only one thread may start the poller
        if not _poller_started:  # First request only
            start_poller(ESP_URL, DB_PATH, get_metadata, stop_event, 1.0, logger)
            _poller_started = True  # Remember that it is running


@app.before_request
def start_background_logging():
    """Kick off continuous logging when someone opens the app."""
    ensure_poller()  # No-op after the first request


@app.route("/")
def index():
    """Render the dashboard HTML page."""
    return render_template("index.html")  # Template in templates/


@app.route("/api/latest")
def latest():
    """Proxy the current ESP32 reading without touching stored data."""
    try:
        r = requests.get(ESP_URL, timeout=2)  # Live GET /data
        return jsonify(r.json())  # Forward the JSON to the browser
    except Exception as e:  # Network or JSON failure
        logger.exception("live proxy failed")  # Log the full traceback
        return jsonify({"error": str(e)})  # Still return valid JSON


@app.route("/api/readings")
def readings():
    """Return stored readings for the requested day (or current capture day)."""
    day = request.args.get("day") or get_metadata()["capture_date"]  # Day filter
    return jsonify(get_readings(DB_PATH, day))  # JSON array of row dicts


@app.route("/api/days")
def days():
    """Return available capture days, newest first, for the day picker."""
    return jsonify(get_days(DB_PATH))  # JSON array of date strings


@app.route("/api/metadata", methods=["POST"])
def set_metadata():
    """Update the capture date and solar angle used for future readings."""
    payload = request.get_json(silent=True) or {}  # JSON body or empty dict
    day = str(payload.get("capture_date", ""))[:10]  # YYYY-MM-DD prefix
    try:
        angle = float(payload.get("solar_angle", 0))  # Numeric degrees
    except (TypeError, ValueError):  # Bad user input
        return jsonify({"error": "solar_angle must be a number"}), 400  # Client error
    if not day:  # Missing date
        return jsonify({"error": "capture_date is required"}), 400  # Client error
    with metadata_lock:  # Hold the lock while updating
        metadata["capture_date"] = day  # New capture day
        metadata["solar_angle"] = angle  # New solar angle
    logger.info("metadata updated: %s", metadata)  # Log the change
    return jsonify(dict(metadata))  # Confirm the new values


@app.route("/api/logs")
def logs():
    """Return the last log lines so the UI can show recent problems."""
    try:
        limit = min(int(request.args.get("limit", 50)), 500)  # Bound the response size
        lines = LOG_PATH.read_text(encoding="utf-8").splitlines()[-limit:]  # Tail of log
    except (OSError, ValueError):  # Missing log file or bad limit
        lines = []  # Nothing to display
    return jsonify(lines)  # JSON array of log lines


@app.route("/export.csv")
def export_csv():
    """Download the selected day's readings as a CSV attachment."""
    day = request.args.get("day") or get_metadata()["capture_date"]  # Day filter
    csv_text = export_day_csv(DB_PATH, day)  # Build CSV from SQLite
    filename = "solarlab_{}.csv".format(day)  # Day in the filename
    return Response(  # Streaming response with download headers
        csv_text,  # CSV body
        mimetype="text/csv",  # Browser recognizes CSV
        headers={"Content-Disposition": "attachment; filename=" + filename},  # Download
    )


if __name__ == "__main__":  # Only run when invoked as a script
    logger.info("starting SolarLab Mini dashboard")  # Startup event
    app.run(host="127.0.0.1", port=5000, debug=True)  # Local development server
```

- [ ] **Step 2: Replace `tests/test_dashboard.py`**

```python
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
```

- [ ] **Step 3: Run all tests**

Run: `PYTHONPATH=/tmp/opencode/dashvenv/lib/python3.14/site-packages python -m pytest tests/ -q`
Expected: PASS (38 tests including storage and poller tests).

- [ ] **Step 4: Commit**

```bash
git add laptop_app/dashboard/app.py tests/test_dashboard.py
git commit -m "feat: add stored readings and metadata routes to dashboard"
```

---

### Task 4: Dashboard UI with three charts and controls

**Files:**
- Modify: `laptop_app/dashboard/templates/index.html`
- Modify: `laptop_app/dashboard/static/style.css`

**Interfaces:**
- Consumes: routes from Task 3.
- Produces: browser UI only; no Python API changes.

- [ ] **Step 1: Replace `laptop_app/dashboard/templates/index.html`**

```html
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>SolarLab Mini Dashboard</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
</head>
<body>
    <h1>SolarLab Mini</h1>
    <div class="cards">
        <div class="card">Voltage: <span id="v">-</span> V</div>
        <div class="card">Current: <span id="i">-</span> A</div>
        <div class="card">Power: <span id="p">-</span> W</div>
    </div>
    <div class="panel">
        <h2>Capture metadata</h2>
        <form id="metadata-form">
            <label for="capture-date">Capture day</label>
            <input type="date" id="capture-date" name="capture_date">
            <label for="solar-angle">Solar angle (degrees)</label>
            <input type="number" id="solar-angle" name="solar_angle" step="any" value="0">
            <button type="submit">Save metadata</button>
        </form>
        <p id="metadata-status"></p>
    </div>
    <div class="panel">
        <h2>Stored readings</h2>
        <label for="day-select">Day</label>
        <select id="day-select"></select>
        <a id="download-csv" href="/export.csv" download>Download CSV</a>
    </div>
    <div class="chart-card"><h2>Voltage</h2><canvas id="voltage-chart"></canvas></div>
    <div class="chart-card"><h2>Current</h2><canvas id="current-chart"></canvas></div>
    <div class="chart-card"><h2>Power</h2><canvas id="power-chart"></canvas></div>
    <div class="panel">
        <h2>Recent events</h2>
        <pre id="log-panel">Loading logs...</pre>
    </div>
    <script>
        // Each chart is created once and updated with fresh rows every second.
        function makeChart(canvasId, label, color) {
            const ctx = document.getElementById(canvasId).getContext('2d');
            return new Chart(ctx, {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [{ label: label, data: [], borderColor: color, borderWidth: 2, pointRadius: 1, fill: false }]
                },
                options: { scales: { x: { ticks: { maxTicksLimit: 10 } }, y: { beginAtZero: true } }, animation: false }
            });
        }

        const voltageChart = makeChart('voltage-chart', 'Voltage (V)', '#1f77b4');
        const currentChart = makeChart('current-chart', 'Current (A)', '#2ca02c');
        const powerChart = makeChart('power-chart', 'Power (W)', '#d62728');

        // Apply one day's rows to all three charts.
        function drawCharts(rows) {
            const labels = rows.map(r => new Date(r.recorded_at * 1000).toLocaleTimeString());
            const datasets = [
                [voltageChart, rows.map(r => r.voltage)],
                [currentChart, rows.map(r => r.current)],
                [powerChart, rows.map(r => r.power)]
            ];
            datasets.forEach(([chart, values]) => {
                chart.data.labels = labels;
                chart.data.datasets[0].data = values;
                chart.update();
            });
        }

        // Keep the day picker in sync with the database.
        async function refreshDays() {
            const res = await fetch('/api/days');
            const days = await res.json();
            const select = document.getElementById('day-select');
            const keep = select.value;
            select.innerHTML = '';
            days.forEach(day => {
                const option = document.createElement('option');
                option.value = day;
                option.textContent = day;
                select.appendChild(option);
            });
            if (days.includes(keep)) { select.value = keep; }
            document.getElementById('download-csv').href = '/export.csv?day=' + encodeURIComponent(select.value);
            return select.value;
        }

        // Refresh live cards, charts, and the log panel.
        async function refresh() {
            try {
                const latest = await (await fetch('/api/latest')).json();
                if (latest.voltage !== undefined) {
                    document.getElementById('v').textContent = latest.voltage;
                    document.getElementById('i').textContent = latest.current;
                    document.getElementById('p').textContent = latest.power;
                }
                const day = await refreshDays();
                if (day) {
                    const rows = await (await fetch('/api/readings?day=' + encodeURIComponent(day))).json();
                    drawCharts(rows);
                }
                const logs = await (await fetch('/api/logs?limit=30')).json();
                document.getElementById('log-panel').textContent = logs.join('\n') || 'No events yet.';
            } catch (e) {
                document.getElementById('log-panel').textContent = 'Dashboard error: ' + e;
            }
        }

        // Save the manual angle and capture day used for future readings.
        document.getElementById('metadata-form').addEventListener('submit', async function (event) {
            event.preventDefault();
            const body = {
                capture_date: document.getElementById('capture-date').value,
                solar_angle: parseFloat(document.getElementById('solar-angle').value)
            };
            const res = await fetch('/api/metadata', {
                method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body)
            });
            const result = await res.json();
            document.getElementById('metadata-status').textContent = JSON.stringify(result);
            refresh();
        });

        document.getElementById('day-select').addEventListener('change', refresh);
        setInterval(refresh, 1000);
        refresh();
    </script>
</body>
</html>
```

- [ ] **Step 2: Replace `laptop_app/dashboard/static/style.css`**

```css
/* SolarLab Mini dashboard styling: simple cards, panels, and stacked charts. */
body { font-family: Arial, sans-serif; margin: 20px; background: #f7f7f7; }
h1 { color: #333; }
h2 { color: #444; font-size: 1.1rem; }
.cards { display: flex; gap: 20px; margin-bottom: 20px; }
.card { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
.panel { background: white; padding: 16px; margin-bottom: 16px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
.panel label { margin-right: 8px; }
.panel input { margin-right: 12px; padding: 4px; }
.panel button, .panel a { padding: 6px 10px; margin-left: 8px; }
.chart-card { background: white; padding: 16px; margin-bottom: 16px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); height: 240px; }
.chart-card canvas { max-height: 190px; }
#log-panel { background: #222; color: #eee; padding: 12px; border-radius: 6px; max-height: 180px; overflow: auto; white-space: pre-wrap; }
```

- [ ] **Step 3: Verify and commit**

Run: `PYTHONPATH=/tmp/opencode/dashvenv/lib/python3.14/site-packages python -m pytest tests/ -q`
Expected: PASS (38 tests).

```bash
git add laptop_app/dashboard/templates/index.html laptop_app/dashboard/static/style.css
git commit -m "feat: graph voltage, current, power with metadata and CSV controls"
```

---

### Task 5: Documentation updates and push

**Files:**
- Modify: `README.md`, `team knowledge/README.md`

**Interfaces:**
- Consumes: all earlier tasks.
- Produces: docs describing the new dashboard routes, files, and Docker being phase 2.

- [ ] **Step 1: Update `README.md`**

In the Laptop App section, add: the dashboard now logs readings to
`laptop_app/dashboard/data/solarlab.sqlite3` and `app.log` while it is open; the page
has a capture date/solar angle form, day picker, three charts, CSV download button,
and recent-events panel; list routes `/api/readings`, `/api/days`, `/api/metadata`,
`/api/logs`, `/export.csv`. Note that Docker packaging is planned as phase 2.

- [ ] **Step 2: Update `team knowledge/README.md`**

Add the same dashboard features to the component table and quick start, explaining
that metadata tags future readings and CSV export is filtered by the selected day.

- [ ] **Step 3: Verify and push**

Run: `PYTHONPATH=/tmp/opencode/dashvenv/lib/python3.14/site-packages python -m pytest tests/ -q`
Expected: PASS (38 tests).

```bash
git add README.md "team knowledge/README.md"
git commit -m "docs: describe dashboard storage and export features"
git push origin master
```

Expected: `git status -sb` shows `## master...origin/master` with no ahead/behind.
