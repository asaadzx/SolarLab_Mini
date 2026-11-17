# Docker packaging design (phase 2)

## Context

Phase 1 is complete and pushed: the Flask dashboard polls the ESP32 once per second,
stores readings in SQLite, tags them with a manual capture date/solar angle, draws
three charts, exports CSV, and shows rotating app logs. The full host suite passes
with 38 tests. Today the app is started manually with `python dashboard/app.py`.

The user wants a Docker image for the dashboard with persistent SQLite/log storage.
The laptop must remain able to reach the ESP32 access point at `192.168.4.1/data`.
The chosen approach is a minimal single-stage image, dashboard only, with Compose
preconfigured for host networking and a named volume.

## Goals

1. Build a small Docker image that runs only the Flask dashboard with Flask and requests.
2. Keep `solarlab.sqlite3` and `app.log` in a Docker named volume across rebuilds/restarts.
3. Use host networking so the container can reach the ESP32 AP directly.
4. Make the app's ESP URL, DB/log paths, and bind address configurable by environment variables.
5. Stream log events to stdout as well as the rotating file for `docker logs`.
6. Document build/run/volume commands and verify the container with a stub sensor when Docker is available.

## Non-goals

- No firmware or ESP32 JSON schema changes.
- No `receiver_http.py`, pandas, pytest, or debug tools inside the image.
- No authentication, reverse proxy, TLS, or multi-container architecture.
- No cloud deployment or orchestration beyond local Docker Compose.
- No change to the SQLite schema or CSV format from phase 1.
- No port mapping; host networking is a deliberate requirement.

## Design

### Files

- `Dockerfile` at the repository root:
  - Base `python:3.12-slim`.
  - Set `WORKDIR /app/laptop_app/dashboard`.
  - Copy and install `laptop_app/requirements-docker.txt` with `pip install --no-cache-dir`.
  - Copy only `laptop_app/dashboard/` into the same workdir so templates and static files are included.
  - Create `/app/data`, assign it to non-root UID/GID `10001`, then switch to that user.
  - Set `ENV PYTHONUNBUFFERED=1`.
  - Expose 5000 for documentation clarity; with host networking no publish step is needed.
  - `CMD ["python", "app.py"]`.
- `laptop_app/requirements-docker.txt`:
  - Exactly `flask` and `requests`, one per line.
  - Kept separate from `laptop_app/requirements.txt` so pandas is not installed in the image.
- `docker-compose.yml` at the repository root:
  - One service named `dashboard`.
  - `build: .`
  - `network_mode: host`
  - `restart: unless-stopped`
  - Top-level named volume `solarlab-data` mounted at `/app/data`.
  - Environment:
    - `ESP_URL=${ESP_URL:-http://192.168.4.1/data}`
    - `SOLARLAB_DB_PATH=/app/data/solarlab.sqlite3`
    - `SOLARLAB_LOG_PATH=/app/data/app.log`
    - `HOST=0.0.0.0`
    - `PORT=5000`
  - No `ports:` section.
- `.dockerignore` at the repository root:
  - Ignore `.git`, `.worktrees`, `laptop_app/.venv`, `__pycache__`, `*.pyc`, `.pytest_cache`,
    `laptop_app/dashboard/data`, firmware/build folders, and the generated Word document.
- `laptop_app/dashboard/app.py`:
  - `ESP_URL` defaults to `http://192.168.4.1/data` but reads the `ESP_URL` environment variable.
  - `DB_PATH` defaults to the existing host path but reads `SOLARLAB_DB_PATH`.
  - `LOG_PATH` defaults to the existing host path but reads `SOLARLAB_LOG_PATH`.
  - `HOST` defaults to `127.0.0.1` and `PORT` defaults to `5000`; both are used only by the `__main__` block.
  - Configure a `StreamHandler(sys.stdout)` in addition to the existing `RotatingFileHandler`.
  - Keep Flask debug mode off in the container; the `__main__` block uses `debug=False`.
  - Keep all existing routes, metadata locking, poller startup, and CSV behavior unchanged.

### Data flow

1. The host joins `SolarLab-Mini`, so `192.168.4.1` is reachable from the host network namespace.
2. Compose starts the container with host networking; the poller inside the container fetches `ESP_URL`.
3. Each fetched reading is inserted into the SQLite file at `SOLARLAB_DB_PATH` on the named volume.
4. App events/errors are written to `SOLARLAB_LOG_PATH` on the same volume and to stdout.
5. Browser requests hit `http://127.0.0.1:5000` (or `http://<laptop-ip>:5000`) and read the same DB/log files.
6. Restarting or rebuilding the container reuses the named volume; `init_db` remains idempotent.

### Error handling

- If the ESP32 is unreachable, the poller logs the failure and retries next interval; the container keeps running.
- `/api/latest` continues to return `{"error": "..."}` with HTTP 200 on a failed live proxy.
- The app creates the DB/log parent directory at startup, so a fresh named volume works without manual setup.
- The non-root user owns `/app/data`, so SQLite writes and log rotation cannot fail from permissions.
- Debug mode is disabled in container execution to avoid duplicate reloader threads.
- No secrets are logged or passed into the container.

### Testing

- `tests/test_docker_config.py`:
  - Monkeypatch the relevant environment variables and reload the dashboard module to verify
    `ESP_URL`, `DB_PATH`, `LOG_PATH`, `HOST`, and `PORT` overrides.
  - Verify the app logger has both a `RotatingFileHandler` and a `StreamHandler`.
  - Restore the module after each test so other tests keep their defaults.
- Existing 38 host tests must still pass unchanged, except for import setup needed by the config tests.
- When Docker is available, perform a container smoke test:
  - `docker compose config` succeeds.
  - `docker compose build` succeeds.
  - Start a local stub sensor on the host and run Compose with `ESP_URL=http://127.0.0.1:<stub-port>/data`.
  - Request `/` and `/api/latest` from `http://127.0.0.1:5000`.
  - Wait for `/api/readings` to show at least one stored row.
  - Restart the container and confirm the row remains in `/api/readings`.
  - Inspect `docker logs` for app events.
- If Docker is unavailable in this environment, report that clearly and rely on config tests plus Compose syntax validation.

### Documentation

- Replace the “Docker packaging is planned as phase 2” note in `README.md` with:
  - Build: `docker compose build`.
  - Run: join `SolarLab-Mini`, then `docker compose up -d`.
  - Open: `http://127.0.0.1:5000`.
  - Logs: `docker compose logs -f dashboard`.
  - Stop: `docker compose down` (volume is preserved).
  - Reset/backup: `docker volume inspect solarlab-data` and a `docker run --rm -v ... tar` example for backup.
  - Note that host networking is Linux-oriented and that the laptop must be on the ESP AP.
- Update `team knowledge/README.md` with the same Docker quick-start steps and regenerate
  `team knowledge/Team Knowledge.docx` from the Markdown source.

## Acceptance criteria

- `docker compose config` reports a valid configuration with host networking and the named volume.
- The image builds and starts with `docker compose up -d`.
- The dashboard renders and `/api/latest` returns the ESP JSON (or a stub JSON during verification).
- At least one reading persists in the named volume across a container restart.
- `docker logs` shows dashboard events in addition to `app.log`.
- Full host test suite passes, including new env-config/logging tests.
- README and team knowledge docs no longer describe Docker as future work.
