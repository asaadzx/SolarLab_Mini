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
