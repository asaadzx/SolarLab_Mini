# Docker Packaging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Package the phase 1 Flask dashboard as a minimal Docker image with host networking, persistent SQLite/log storage, environment-based configuration, and container-log visibility.

**Architecture:** Add a root Dockerfile, Compose file, `.dockerignore`, and dashboard-only requirements file. Make `app.py` read environment overrides and add a stdout log handler, then verify config tests, Compose syntax, an optional real container smoke test, and docs.

**Tech Stack:** Docker, Docker Compose, Python 3.12-slim, Flask, requests, pytest.

## Global Constraints

- Base `python:3.12-slim`.
- Dependencies exactly `flask` and `requests`; no pandas/pytest in the image.
- Host networking, no port mapping; ESP URL default `http://192.168.4.1/data`.
- Named volume `solarlab-data` at `/app/data`.
- Non-root UID/GID `10001`.
- Env overrides: `ESP_URL`, `SOLARLAB_DB_PATH`, `SOLARLAB_LOG_PATH`, `HOST`, `PORT`.
- Compose supports `ESP_URL=${ESP_URL:-http://192.168.4.1/data}`.
- Debug mode is off in container execution.
- Comments are required on every new function and variable.
- If Docker is unavailable in this environment, report that clearly and rely on config tests plus Compose syntax validation.

---

### Task 1: Environment configuration and stdout logging

**Files:**
- Modify: `laptop_app/dashboard/app.py`
- Create: `tests/test_docker_config.py`

**Interfaces:**
- Consumes: existing dashboard module globals and logger.
- Produces: `ESP_URL`, `DB_PATH`, `LOG_PATH`, `HOST`, `PORT`, and a logger with `RotatingFileHandler` + stdout `StreamHandler`.

- [ ] **Step 1: Write the failing tests**

```python
import importlib
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

import pytest

pytest.importorskip("flask")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "laptop_app" / "dashboard"))

import app as dashboard  # noqa: E402

ENV_KEYS = (  # Environment variables managed by this test module
    "ESP_URL",  # Sensor endpoint override
    "SOLARLAB_DB_PATH",  # SQLite path override
    "SOLARLAB_LOG_PATH",  # Log path override
    "HOST",  # Bind address override
    "PORT",  # Bind port override
)


@pytest.fixture
def reloaded_app(monkeypatch, tmp_path):
    """Reload the dashboard module with deterministic environment overrides."""
    app_logger = logging.getLogger("solarlab.dashboard")  # Named logger under test
    for handler in list(app_logger.handlers):  # Remove handlers from prior reloads
        app_logger.removeHandler(handler)  # Detach one old handler

    env = {  # Values injected for this test
        "ESP_URL": "http://127.0.0.1:18765/data",  # Stub sensor endpoint
        "SOLARLAB_DB_PATH": str(tmp_path / "db.sqlite3"),  # Temporary DB path
        "SOLARLAB_LOG_PATH": str(tmp_path / "app.log"),  # Temporary log path
        "HOST": "0.0.0.0",  # Container-style bind address
        "PORT": "5055",  # Non-default port
    }
    for key, value in env.items():  # Apply every override
        monkeypatch.setenv(key, value)  # Set one environment variable

    module = importlib.reload(dashboard)  # Re-import app.py with overrides
    yield module  # Hand the reloaded module to the test

    for handler in list(app_logger.handlers):  # Clean up the reloaded handlers
        app_logger.removeHandler(handler)  # Detach one handler
    for key in ENV_KEYS:  # Remove injected environment variables
        monkeypatch.delenv(key, raising=False)  # Delete one variable if present
    importlib.reload(dashboard)  # Restore default module state


def test_environment_overrides(reloaded_app, tmp_path):
    """Verify every Docker environment override reaches the app module."""
    assert reloaded_app.ESP_URL == "http://127.0.0.1:18765/data"
    assert reloaded_app.DB_PATH == tmp_path / "db.sqlite3"
    assert reloaded_app.LOG_PATH == tmp_path / "app.log"
    assert reloaded_app.HOST == "0.0.0.0"
    assert reloaded_app.PORT == 5055


def test_logger_has_file_and_stdout_handlers(reloaded_app):
    """Verify the logger writes to both app.log and Docker stdout."""
    handlers = reloaded_app.logger.handlers
    assert any(isinstance(handler, RotatingFileHandler) for handler in handlers)
    assert any(
        isinstance(handler, logging.StreamHandler)
        and not isinstance(handler, RotatingFileHandler)
        for handler in handlers
    )
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `PYTHONPATH=/tmp/opencode/dashvenv/lib/python3.14/site-packages /home/asaad/.local/share/mise/installs/python/3.14.3/bin/python3.14 -m pytest tests/test_docker_config.py -q`
Expected: FAIL because `app.py` does not yet read env vars or add a stdout handler.

- [ ] **Step 3: Replace `laptop_app/dashboard/app.py`**

```python
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
```

- [ ] **Step 4: Run focused and full tests**

Run: `PYTHONPATH=/tmp/opencode/dashvenv/lib/python3.14/site-packages /home/asaad/.local/share/mise/installs/python/3.14.3/bin/python3.14 -m pytest tests/test_docker_config.py -q`
Expected: PASS (2 tests).

Run: `PYTHONPATH=/tmp/opencode/dashvenv/lib/python3.14/site-packages /home/asaad/.local/share/mise/installs/python/3.14.3/bin/python3.14 -m pytest tests/ -q`
Expected: PASS (40 tests).

- [ ] **Step 5: Commit**

```bash
git add laptop_app/dashboard/app.py tests/test_docker_config.py
git commit -m "feat: make dashboard container configurable"
```

---

### Task 2: Docker build files and Compose configuration

**Files:**
- Create: `Dockerfile`
- Create: `laptop_app/requirements-docker.txt`
- Create: `.dockerignore`
- Create: `docker-compose.yml`

**Interfaces:**
- Consumes: env overrides from Task 1.
- Produces: buildable image and valid Compose configuration; no Python API changes.

- [ ] **Step 1: Create `laptop_app/requirements-docker.txt`**

```text
# Container runtime dependencies only; pandas is not needed by the dashboard.
flask
requests
```

- [ ] **Step 2: Create `Dockerfile`**

```dockerfile
# Minimal single-stage image for the SolarLab Mini dashboard.
FROM python:3.12-slim

# Keep Python output unbuffered and avoid bytecode files in the image.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# The app is launched from its own directory.
WORKDIR /app/laptop_app/dashboard

# Install only the dashboard runtime dependencies.
COPY laptop_app/requirements-docker.txt /app/laptop_app/requirements-docker.txt
RUN pip install --no-cache-dir -r /app/laptop_app/requirements-docker.txt

# Copy the dashboard code, templates, and static files.
COPY laptop_app/dashboard/ /app/laptop_app/dashboard/

# Prepare the persistent data directory for the non-root user.
RUN mkdir -p /app/data && chown -R 10001:10001 /app/data
USER 10001:10001

# Documented port; host networking means no docker -p flag is needed.
EXPOSE 5000

# Run the Flask development server with debug disabled by app.py.
CMD ["python", "app.py"]
```

- [ ] **Step 3: Create `.dockerignore`**

```gitignore
.git
.worktrees
laptop_app/.venv
**/__pycache__
*.pyc
.pytest_cache
laptop_app/dashboard/data
firmware
firmware_pio
src
include
test_wifi
.cache
team knowledge/Team Knowledge.docx
```

- [ ] **Step 4: Create `docker-compose.yml`**

```yaml
services:
  dashboard:
    build: .
    image: solarball-mini-dashboard
    container_name: solarball-mini-dashboard
    network_mode: host
    restart: unless-stopped
    environment:
      ESP_URL: "${ESP_URL:-http://192.168.4.1/data}" # Sensor endpoint, overrideable for stub tests
      SOLARLAB_DB_PATH: /app/data/solarlab.sqlite3 # SQLite file inside the named volume
      SOLARLAB_LOG_PATH: /app/data/app.log # Rotating log inside the named volume
      HOST: 0.0.0.0 # Bind all host interfaces under host networking
      PORT: "5000" # Dashboard port
    volumes:
      - solarlab-data:/app/data # Persistent DB and logs

volumes:
  solarlab-data:
    name: solarlab-data
```

- [ ] **Step 5: Verify Compose syntax**

Run: `docker compose config`
Expected: prints the resolved config with `network_mode: host`, `solarlab-data:/app/data`, and the five environment variables. If Docker is unavailable, record `docker compose` not available and continue to the commit.

- [ ] **Step 6: Commit**

```bash
git add Dockerfile laptop_app/requirements-docker.txt .dockerignore docker-compose.yml
git commit -m "feat: add Docker image and Compose configuration"
```

---

### Task 3: Container smoke verification

**Files:**
- No repository files are changed by this task.
- Uses temporary files `/tmp/solarlab-stub.py`, `/tmp/solarlab-stub.log`, and `/tmp/solarlab-stub.pid`.

**Interfaces:**
- Consumes: Compose config from Task 2 and env overrides from Task 1.
- Produces: verification evidence only.

- [ ] **Step 1: Check Docker availability**

Run: `docker version --format '{{.Server.Version}}'`
Expected: prints a Docker server version. If it fails, skip Steps 2-7, report that the container smoke test was not run locally, and continue to Task 4.

- [ ] **Step 2: Write the temporary stub sensor**

Write `/tmp/solarlab-stub.py`:

```python
"""Temporary stub sensor for Docker container verification."""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PAYLOAD = {"voltage": 4.5, "current": 0.1, "power": 0.45, "timestamp": 1}  # Fixed sensor reading


class StubHandler(BaseHTTPRequestHandler):
    """Serve one fixed sensor payload on every GET."""

    def do_GET(self):
        """Return the fixed JSON payload with a correct Content-Length."""
        body = json.dumps(PAYLOAD).encode()  # JSON bytes sent to the client
        self.send_response(200)  # Success status
        self.send_header("Content-Type", "application/json")  # JSON content type
        self.send_header("Content-Length", str(len(body)))  # Exact body length
        self.end_headers()  # Finish response headers
        self.wfile.write(body)  # Write the JSON body

    def log_message(self, *args):
        """Silence default request logging for the temporary stub."""
        pass  # No per-request output


ThreadingHTTPServer(("127.0.0.1", 18765), StubHandler).serve_forever()
```

- [ ] **Step 3: Build and start the container against the stub**

```bash
/usr/bin/python3 /tmp/solarlab-stub.py > /tmp/solarlab-stub.log 2>&1 &
echo $! > /tmp/solarlab-stub.pid
docker compose build
ESP_URL=http://127.0.0.1:18765/data docker compose up -d
```

Expected: build succeeds and `docker compose ps` shows `solarball-mini-dashboard` running.

- [ ] **Step 4: Verify HTTP routes**

```bash
for i in $(seq 1 30); do curl -fsS http://127.0.0.1:5000/ >/dev/null && break; sleep 1; done
curl -fsS http://127.0.0.1:5000/api/latest
```

Expected: first command returns no output on success; `/api/latest` prints the stub payload.

- [ ] **Step 5: Verify stored reading and persistence**

```bash
TODAY=$(date +%F)
for i in $(seq 1 15); do ROWS=$(curl -fsS "http://127.0.0.1:5000/api/readings?day=$TODAY"); [ "$ROWS" != "[]" ] && break; sleep 1; done
printf '%s\n' "$ROWS"
docker compose restart dashboard
for i in $(seq 1 30); do curl -fsS http://127.0.0.1:5000/ >/dev/null && break; sleep 1; done
curl -fsS "http://127.0.0.1:5000/api/readings?day=$TODAY"
```

Expected: both reading outputs contain at least one row with `voltage`, `current`, `power`, and `solar_angle`.

- [ ] **Step 6: Verify container logs and clean up**

```bash
docker compose logs --tail=20 dashboard
docker compose down
kill "$(cat /tmp/solarlab-stub.pid)"
rm -f /tmp/solarlab-stub.py /tmp/solarlab-stub.log /tmp/solarlab-stub.pid
```

Expected: logs show dashboard events; Compose stops; stub process is gone.

- [ ] **Step 7: Commit verification results**

There are no repository changes. Append the exact commands and observed output to `/tmp/opencode/docker-smoke-report.txt` instead of creating a commit.

---

### Task 4: Documentation updates and final verification

**Files:**
- Modify: `README.md`
- Modify: `team knowledge/README.md`
- Regenerate: `team knowledge/Team Knowledge.docx`

**Interfaces:**
- Consumes: Docker files from Task 2 and verification evidence from Task 3.
- Produces: docs that describe the shipped container workflow.

- [ ] **Step 1: Replace the Docker note in `README.md`**

Replace this line:

```markdown
Docker packaging is planned as phase 2 and is not part of the current setup.
```

with this section:

````markdown
## Docker (host networking)

The dashboard can run as a minimal container. The laptop must be joined to
`SolarLab-Mini` so the container can reach `192.168.4.1/data` through host
networking; there is no `ports:` mapping.

```bash
docker compose build
docker compose up -d
# Open http://127.0.0.1:5000
docker compose logs -f dashboard
docker compose down
```

SQLite and rotating logs live in the `solarlab-data` named volume at
`/app/data`. `docker compose down` preserves it. To back it up:

```bash
docker run --rm -v solarlab-data:/data -v "$PWD":/backup alpine \
  tar czf /backup/solarlab-data-backup.tgz -C /data .
```

For testing without the board, set `ESP_URL` before `docker compose up`, for
example `ESP_URL=http://127.0.0.1:18765/data docker compose up -d`.
````

- [ ] **Step 2: Update `team knowledge/README.md`**

Change step 7 from “Docker packaging is planned as phase 2, so run the app directly
with Python for now.” to:

```markdown
7. Use the CSV download button to export the selected day's readings, and the
   recent-events panel to see the latest log lines. To run in Docker instead of
   directly with Python, join `SolarLab-Mini`, then run `docker compose build`
   and `docker compose up -d`; open `http://127.0.0.1:5000`. SQLite and logs are
   stored in the `solarlab-data` named volume and survive `docker compose down`.
```

Add one row to the component table:

```markdown
| Docker dashboard | Minimal `python:3.12-slim` image and Compose service with host networking, a non-root user, stdout logging, and the `solarlab-data` named volume. |
```

- [ ] **Step 3: Regenerate the Word document**

Run: `PYTHONPATH=/tmp/opencode/dashvenv/lib/python3.14/site-packages /home/asaad/.local/share/mise/installs/python/3.14.3/bin/python3.14 "team knowledge/generate_docx.py"`
Expected: `team knowledge/Team Knowledge.docx` is regenerated without error.

- [ ] **Step 4: Run final verification**

Run: `PYTHONPATH=/tmp/opencode/dashvenv/lib/python3.14/site-packages /home/asaad/.local/share/mise/installs/python/3.14.3/bin/python3.14 -m pytest tests/ -q`
Expected: PASS (40 tests).

Run: `docker compose config`
Expected: valid config. If Docker is unavailable, record that from Task 3 and rely on the host tests.

- [ ] **Step 5: Commit**

```bash
git add README.md "team knowledge/README.md" "team knowledge/Team Knowledge.docx"
git commit -m "docs: document Docker dashboard workflow"
```
