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
