import csv  # Parse the exported CSV text in tests
import io  # Wrap CSV text in an in-memory file-like object
import sys  # Allow importing the dashboard module from the test suite
from pathlib import Path  # Build temporary database paths

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "laptop_app" / "dashboard"))  # Expose the dashboard package directory

from storage import CSV_HEADER, export_day_csv, get_days, get_readings, init_db, insert_reading  # noqa: E402


def test_init_db_creates_table(tmp_path):
    """Creating the database also creates missing parent folders."""
    db_path = tmp_path / "nested" / "readings.sqlite3"  # Nested path exercises folder creation
    init_db(db_path)
    assert db_path.exists() is True
    assert get_readings(db_path, "2026-11-17") == []


def test_insert_and_query_by_day(tmp_path):
    """Readings are filtered by capture day and days are listed newest first."""
    db_path = tmp_path / "readings.sqlite3"  # Database file supplied by pytest
    init_db(db_path)
    insert_reading(db_path, 100.0, "2026-11-17", 15.0, 4.5, 0.1, 0.45)
    insert_reading(db_path, 101.0, "2026-11-18", 30.0, 4.6, 0.2, 0.92)
    rows = get_readings(db_path, "2026-11-17")  # Only the first day should match
    assert len(rows) == 1
    assert rows[0]["solar_angle"] == 15.0
    assert get_days(db_path) == ["2026-11-18", "2026-11-17"]


def test_export_day_csv_contains_metadata(tmp_path):
    """CSV export includes capture metadata alongside the sensor values."""
    db_path = tmp_path / "readings.sqlite3"  # Database file supplied by pytest
    init_db(db_path)
    insert_reading(db_path, 100.0, "2026-11-17", 15.0, 4.5, 0.1, 0.45)
    text = export_day_csv(db_path, "2026-11-17")  # Full CSV document for one day
    rows = list(csv.DictReader(io.StringIO(text)))  # Parsed rows keyed by header
    assert rows[0]["capture_date"] == "2026-11-17"
    assert rows[0]["solar_angle"] == "15.0"
    assert list(rows[0].keys()) == CSV_HEADER
