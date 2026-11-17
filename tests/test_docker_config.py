import importlib
import logging
import os
import shutil
import subprocess
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

APP_MODULES = ("app.py", "poller.py", "storage.py")  # Modules needed by an isolated import
IMPORT_DRIVER = "import app; print('IMPORTED')"  # Prove app.py imports without starting the server


def import_app_from_read_only_dir(tmp_path):
    """Import app.py from a non-writable module directory like the container."""
    source_dir = Path(__file__).resolve().parent.parent / "laptop_app" / "dashboard"  # Real app source
    sandbox_dir = tmp_path / "sandbox" / "dashboard"  # Isolated module directory
    data_dir = tmp_path / "data"  # Writable env-configured data directory
    sandbox_dir.mkdir(parents=True)  # Create the isolated module directory
    data_dir.mkdir()  # Create the writable data directory

    for module_name in APP_MODULES:  # Copy each runtime module into the sandbox
        shutil.copy2(source_dir / module_name, sandbox_dir / module_name)  # Copy one module

    environment = os.environ.copy()  # Inherit the test Python environment
    environment["SOLARLAB_DB_PATH"] = str(data_dir / "solarlab.sqlite3")  # Redirect the DB
    environment["SOLARLAB_LOG_PATH"] = str(data_dir / "app.log")  # Redirect the log
    sandbox_dir.chmod(0o555)  # Simulate a root-owned, non-writable app directory
    try:
        return subprocess.run(  # Import the sandboxed app in a fresh Python process
            [sys.executable, "-c", IMPORT_DRIVER],  # Command that imports app.py
            cwd=sandbox_dir,  # Make the sandbox the import root
            env=environment,  # Use env-configured writable data paths
            capture_output=True,  # Capture stdout and stderr
            text=True,  # Return text instead of bytes
            timeout=10,  # Avoid hanging if the app starts a server
        )
    finally:
        sandbox_dir.chmod(0o755)  # Restore write permission for pytest cleanup


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


def test_app_imports_without_writable_default_data_dir(tmp_path):
    """Verify container-style imports do not need a writable default data dir."""
    result = import_app_from_read_only_dir(tmp_path)  # Import from the simulated container layout
    assert result.returncode == 0, result.stderr  # Import must succeed without PermissionError
    assert "IMPORTED" in result.stdout  # Confirm app.py reached the end of import
