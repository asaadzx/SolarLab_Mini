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
