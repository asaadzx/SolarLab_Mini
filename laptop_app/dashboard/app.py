"""Flask dashboard with stored readings, metadata, CSV export, and logs."""

import logging  # Application event/error logging
import os  # Read environment-variable overrides
import sys  # Stream log events to stdout for Docker
import threading  # Protect shared metadata and poller startup
from datetime import date  # Default capture day
from logging.handlers import RotatingFileHandler  # Rotating log file
from pathlib import Path  # Filesystem paths

from flask import Flask, Response, jsonify, render_template, request  # Web framework
import requests  # Live proxy to the ESP32

from poller import start_poller  # Background logger thread
from storage import export_day_csv, get_days, get_readings, init_db  # Database helpers

ESP_URL = os.getenv("ESP_URL", "http://192.168.4.1/data")  # ESP32 JSON endpoint
BASE_DIR = Path(__file__).resolve().parent  # Folder containing this app
DATA_DIR = BASE_DIR / "data"  # Default folder for DB and log files
DB_PATH = Path(os.getenv("SOLARLAB_DB_PATH", str(DATA_DIR / "solarlab.sqlite3")))  # SQLite DB file
LOG_PATH = Path(os.getenv("SOLARLAB_LOG_PATH", str(DATA_DIR / "app.log")))  # Rotating log file
HOST = os.getenv("HOST", "127.0.0.1")  # Bind address used by the dev server
PORT = int(os.getenv("PORT", "5000"))  # Bind port used by the dev server

app = Flask(__name__)  # Flask application object
DATA_DIR.mkdir(parents=True, exist_ok=True)  # Create default data folder on startup
metadata = {"capture_date": date.today().isoformat(), "solar_angle": 0.0}  # Current tags
metadata_lock = threading.Lock()  # Guards metadata reads/writes
_poller_started = False  # Prevents duplicate poller threads
_poller_lock = threading.Lock()  # Guards poller startup
stop_event = threading.Event()  # Signals the poller to stop

logger = logging.getLogger("solarlab.dashboard")  # Named application logger
logger.setLevel(logging.INFO)  # Record info and above
if not logger.handlers:  # Configure handlers only once
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)  # Ensure the log folder exists
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")  # Shared log format
    file_handler = RotatingFileHandler(  # Keeps logs bounded in size
        str(LOG_PATH), maxBytes=1_000_000, backupCount=3  # 1 MB x 4 files
    )
    file_handler.setFormatter(formatter)  # Apply shared format to file logs
    logger.addHandler(file_handler)  # Attach the rotating file handler
    stream_handler = logging.StreamHandler(sys.stdout)  # Send events to Docker logs
    stream_handler.setFormatter(formatter)  # Apply shared format to stdout logs
    logger.addHandler(stream_handler)  # Attach the stdout handler

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
    app.run(host=HOST, port=PORT, debug=False)  # Local/container dev server
