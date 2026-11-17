import json  # Build the stub HTTP response body
import logging  # Capture log records emitted by the poller
import sys  # Allow importing the dashboard module from the test suite
import threading  # Run the stub server and poller on background threads
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer  # Stub ESP32 endpoint
from pathlib import Path  # Build temporary database paths

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "laptop_app" / "dashboard"))  # Expose the dashboard package directory

from poller import poll_once, start_poller  # noqa: E402
from storage import get_readings, init_db  # noqa: E402


class StubHandler(BaseHTTPRequestHandler):
    """Serve a fixed ESP32-style JSON payload for poll_once tests."""

    PAYLOAD = {"voltage": 4.5, "current": 0.1, "power": 0.45, "timestamp": 100}  # Sensor reading

    def do_GET(self):
        """Return the stub reading as a JSON HTTP response."""
        body = json.dumps(self.PAYLOAD).encode()  # Serialize the payload to bytes
        self.send_response(200)  # Report success
        self.send_header("Content-Type", "application/json")  # Declare JSON content
        self.send_header("Content-Length", str(len(body)))  # Declare body length
        self.end_headers()  # Finish the response headers
        self.wfile.write(body)  # Send the JSON body

    def log_message(self, *args):
        """Silence the default HTTP server request logging."""
        pass  # Intentionally discard request log lines


def test_poll_once_stores_tagged_reading(tmp_path):
    """A single poll stores the ESP32 reading tagged with capture metadata."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), StubHandler)  # Stub server on a free port
    thread = threading.Thread(target=server.serve_forever, daemon=True)  # Serve in background
    thread.start()  # Begin serving requests
    host, port = server.server_address[:2]  # Bound address of the stub server
    db_path = tmp_path / "readings.sqlite3"  # Database file supplied by pytest
    init_db(db_path)  # Create the readings table
    metadata = {"capture_date": "2026-11-17", "solar_angle": 25.0}  # Manual capture tags
    poll_once("http://{}:{}/data".format(host, port), db_path, metadata)  # Fetch and store one row
    rows = get_readings(db_path, "2026-11-17")  # Read back the stored day
    assert len(rows) == 1  # Exactly one reading was stored
    assert rows[0]["solar_angle"] == 25.0  # Solar angle tag was preserved
    assert rows[0]["voltage"] == 4.5  # Sensor voltage was stored
    server.shutdown()  # Stop the stub server loop
    server.server_close()  # Release the listening socket
    thread.join(timeout=2)  # Wait for the server thread to exit


def test_start_poller_logs_failure_and_stops(tmp_path):
    """A failed poll is logged and the poller thread stops on the stop event."""
    db_path = tmp_path / "readings.sqlite3"  # Database file supplied by pytest
    init_db(db_path)  # Create the readings table
    stop_event = threading.Event()  # Signal used to stop the poller
    metadata = {"capture_date": "2026-11-17", "solar_angle": 0.0}  # Manual capture tags
    records = []  # Collected log messages

    class Capture(logging.Handler):
        """Logging handler that records messages and stops the poller."""

        def emit(self, record):
            """Capture one log record and signal the loop to stop."""
            records.append(record.getMessage())  # Store the formatted message
            stop_event.set()  # The first failed poll ends the loop

    logger = logging.getLogger("test-poller")  # Isolated logger for the test
    logger.addHandler(Capture())  # Attach the capturing handler
    logger.setLevel(logging.INFO)  # Capture INFO and above
    worker = start_poller(  # Start the background poller
        "http://127.0.0.1:1/data", db_path, lambda: metadata,  # Unreachable endpoint
        stop_event, interval=0.01, logger=logger,  # Fast loop with test logger
    )
    worker.join(timeout=2)  # Wait for the thread to finish
    assert worker.is_alive() is False  # Thread exited after the stop event
    assert any("poll failed" in line for line in records)  # Failure was logged
