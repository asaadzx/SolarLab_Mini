# Dashboard data, storage, and logging design (phase 1)

## Context

The current Flask app in `laptop_app/dashboard/app.py` only proxies the ESP32's
`http://192.168.4.1/data` response to a browser. `index.html` draws one Chart.js
line for power and keeps no history beyond the browser session. `requirements.txt`
already contains Flask and requests; the current test suite has 30 passing host
tests, including three dashboard tests that use a local stub sensor.

The user wants the app to log readings continuously while it runs, record a manual
solar angle and capture day, graph voltage/current/power, download CSV for a chosen
day, keep data in SQLite on the machine, and log its own problems to a file shown
in the UI. Docker packaging is a separate, second phase.

## Goals

1. Poll the ESP32 once per second in a background thread and persist every reading.
2. Let the user set a capture date and solar angle that tag subsequent readings.
3. Show three charts (voltage, current, power) for a selected capture day.
4. Allow CSV download of the selected day's readings, including metadata columns.
5. Log application events/errors to a rotating file and show recent events in the UI.
6. Keep every new function and variable commented heavily, matching the rest of the repo.

## Non-goals

- No Docker image yet (phase 2).
- No changes to the ESP32 firmware or its JSON schema (`voltage`, `current`, `power`, `timestamp`).
- No authentication, multi-user support, or cloud storage.
- No new third-party runtime dependencies; use Python's `sqlite3`, `csv`, `logging`, and `threading`.
- No changes to `laptop_app/receiver_http.py`.

## Design

### Modules

- `laptop_app/dashboard/storage.py` — owns the SQLite file and all SQL/CSV logic.
  - `init_db(db_path: Path) -> None` creates the `readings` table if needed.
  - `insert_reading(db_path, recorded_at, capture_date, solar_angle, voltage, current, power) -> None` appends one row.
  - `get_readings(db_path, capture_date) -> list[dict]` returns that day's rows ordered by time.
  - `get_days(db_path) -> list[str]` returns distinct capture dates, newest first.
  - `export_day_csv(db_path, capture_date) -> str` returns CSV text with header
    `recorded_at,capture_date,solar_angle,voltage,current,power`.
  - Schema: `readings(id INTEGER PRIMARY KEY AUTOINCREMENT, recorded_at REAL NOT NULL,
    capture_date TEXT NOT NULL, solar_angle REAL NOT NULL, voltage REAL, current REAL,
    power REAL)`. Index on `capture_date`.
- `laptop_app/dashboard/poller.py` — owns the background thread.
  - `start_poller(esp_url, db_path, get_metadata, stop_event, interval=1.0) -> threading.Thread`
    starts a daemon thread that fetches `/data`, inserts a reading tagged with the
    current metadata dict (`capture_date`, `solar_angle`), and logs successes/failures.
  - A failed fetch or bad JSON is logged and retried on the next interval; no exception
    escapes the thread.
- `laptop_app/dashboard/app.py` — thin Flask routes plus logging setup.
  - `ESP_URL`, `DB_PATH` (default `laptop_app/dashboard/data/solarlab.sqlite3`),
    `LOG_PATH` (default `laptop_app/dashboard/data/app.log`).
  - Global metadata dict protected by a lock; POST `/api/metadata` updates it.
  - `GET /` renders the page; `GET /api/latest` keeps the existing live proxy behavior.
  - `GET /api/readings?day=YYYY-MM-DD` returns stored rows.
  - `GET /api/days` supplies available days for the picker.
  - `GET /api/logs?limit=50` returns the last log lines.
  - `GET /export.csv?day=YYYY-MM-DD` returns CSV with `text/csv` and a
    `Content-Disposition` attachment filename containing the day.
  - On app creation, initialize the DB, configure a rotating `logging` file handler,
    and start the poller exactly once using a module-level `_poller_started` boolean
    guarded by `_poller_lock` (avoids duplicate threads when Flask debug reloads).
- `laptop_app/dashboard/templates/index.html` — three stacked Chart.js canvases,
  a day `<select>`, metadata form (`type="date"`, `type="number" step="any"` for angle),
  a "Download CSV" link/button, and a `<pre>` panel for recent events. Poll
  `/api/readings`, `/api/days`, and `/api/logs` on an interval.
- `laptop_app/dashboard/static/style.css` — small additions for stacked chart cards
  and the log panel; keep the existing color scheme.

### Data flow

1. Poller reads metadata (date + angle) under a lock, fetches ESP JSON, inserts a row.
2. Browser asks `/api/readings?day=...`; app reads SQLite and returns arrays.
3. Metadata form POSTs to `/api/metadata`; subsequent polled rows carry the new values.
4. CSV export reads the same query used by the chart and streams it as a file.
5. All module errors and notable events go through `logging` to `data/app.log`;
   `/api/logs` reads the tail of that file for the UI panel.

### Error handling

- SQLite connections are opened per operation with `timeout=5` and closed in `finally`.
- A bad `/data` response is logged with the URL and exception text; the poller continues.
- Invalid/missing `day` query parameters default to the current metadata capture date.
- The log panel shows plain text and escapes nothing sensitive (no secrets are logged).

### Testing

- `tests/test_dashboard_storage.py`: temporary DB; verify table creation, insert,
  day ordering, distinct days, and CSV header/content including angle and date.
- Extend `tests/test_dashboard.py`: metadata POST changes tagging of the next polled
  reading; `/api/readings`, `/api/logs`, and `/export.csv` return expected data;
  poller logs a failed fetch and keeps running.
- Use the existing stub HTTP server pattern and `pytest.importorskip("flask")`.
- Full suite must pass with Flask available on `PYTHONPATH` (currently 30 tests before
  additions).

### Documentation

- Update `README.md` and `team knowledge/README.md` with the new dashboard routes,
  SQLite/CSV locations, metadata form, and Docker being planned as phase 2.
