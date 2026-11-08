# ESP32 MicroPython Deploy CLI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `deploy.py`, an interactive CLI that scans serial ports, lets the user pick an ESP32, flashes pinned MicroPython v1.29.0, and uploads the `firmware/` files.

**Architecture:** A single `deploy.py` module with small pure functions for port classification/selection, firmware caching, and subprocess wrappers around `esptool`/`mpremote`. Tests live in `tests/test_deploy.py` and use pytest plus monkeypatching, so no hardware is required.

**Tech Stack:** Python 3, pytest, pyserial, esptool, mpremote.

## Global Constraints

- Pinned firmware: `ESP32_GENERIC-20260824-v1.29.0.bin` from `https://micropython.org/resources/firmware/`.
- Flash address `0x1000`, baud `460800`, chip `esp32`.
- Known ESP32 VIDs: `0x10C4`, `0x1A86`, `0x303A`, `0x0403`.
- No changes to files under `firmware/`.
- Linux/macOS shell only; Python 3.10+.
- Never commit unless the human partner explicitly asks.

---

### Task 1: Port scanning and selection

**Files:**
- Create: `deploy.py`
- Test: `tests/test_deploy.py`

**Interfaces:**
- Produces: `ESP_VIDS: dict[int, str]`, `is_esp_port(port) -> bool`, `format_port(port) -> str`, `scan_ports() -> list`, `select_port(ports, input_fn=input, print_fn=print)`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_deploy.py`:

```python
from types import SimpleNamespace

import deploy


def fake_port(device="/dev/ttyUSB0", description="CP2102 USB to UART", vid=0x10C4, pid=0xEA60):
    return SimpleNamespace(device=device, description=description, vid=vid, pid=pid)


def test_is_esp_port_recognizes_known_vid():
    assert deploy.is_esp_port(fake_port(vid=0x10C4)) is True
    assert deploy.is_esp_port(fake_port(vid=0x1A86)) is True
    assert deploy.is_esp_port(fake_port(vid=0x303A)) is True
    assert deploy.is_esp_port(fake_port(vid=0x0403)) is True


def test_is_esp_port_rejects_unknown_vid():
    assert deploy.is_esp_port(fake_port(vid=0x1234)) is False


def test_is_esp_port_handles_missing_vid():
    assert deploy.is_esp_port(fake_port(vid=None, pid=None)) is False


def test_format_port_marks_esp():
    assert "ESP: yes" in deploy.format_port(fake_port(vid=0x10C4))
    assert "ESP: no" in deploy.format_port(fake_port(vid=0x1234))
    assert "----:----" in deploy.format_port(fake_port(vid=None, pid=None))


def test_select_port_returns_selected_port():
    ports = [fake_port("/dev/ttyUSB0"), fake_port("/dev/ttyUSB1", vid=0x1234)]
    answers = iter(["2"])
    selected = deploy.select_port(ports, input_fn=lambda _: next(answers), print_fn=lambda *_: None)
    assert selected.device == "/dev/ttyUSB1"


def test_select_port_quits():
    ports = [fake_port()]
    selected = deploy.select_port(ports, input_fn=lambda _: "q", print_fn=lambda *_: None)
    assert selected is None


def test_select_port_reprompts_on_invalid_input():
    ports = [fake_port("/dev/ttyUSB0")]
    answers = iter(["99", "1"])
    selected = deploy.select_port(ports, input_fn=lambda _: next(answers), print_fn=lambda *_: None)
    assert selected.device == "/dev/ttyUSB0"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_deploy.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'deploy'`.

- [ ] **Step 3: Write minimal implementation**

Create `deploy.py`:

```python
#!/usr/bin/env python3
"""SolarLab Mini ESP32 MicroPython deploy CLI."""

from __future__ import annotations

try:
    from serial.tools import list_ports
except ImportError:  # pragma: no cover - handled at runtime
    list_ports = None

ESP_VIDS = {
    0x10C4: "CP210x",
    0x1A86: "CH340/CH9102",
    0x303A: "Espressif USB",
    0x0403: "FTDI",
}


def is_esp_port(port) -> bool:
    return port.vid in ESP_VIDS


def format_port(port) -> str:
    if port.vid is None or port.pid is None:
        vid_pid = "----:----"
    else:
        vid_pid = f"{port.vid:04X}:{port.pid:04X}"
    marker = "yes" if is_esp_port(port) else "no"
    return f"{port.device:<20} {port.description:<35} {vid_pid:<10} ESP: {marker}"


def scan_ports() -> list:
    if list_ports is None:
        return []
    return list(list_ports.comports())


def select_port(ports, input_fn=input, print_fn=print):
    print_fn("Detected serial ports:")
    for index, port in enumerate(ports, start=1):
        print_fn(f"  {index}. {format_port(port)}")
    while True:
        choice = input_fn(f"Select ESP32 [1-{len(ports)}] (q to quit): ").strip()
        if choice.lower() == "q":
            return None
        if choice.isdigit() and 1 <= int(choice) <= len(ports):
            return ports[int(choice) - 1]
        print_fn("Invalid selection.")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_deploy.py -v`
Expected: 7 passed.

---

### Task 2: Firmware cache and board commands

**Files:**
- Modify: `deploy.py`
- Test: `tests/test_deploy.py`

**Interfaces:**
- Consumes: nothing from Task 1 beyond the module.
- Produces: `MICROPYTHON_VERSION`, `FIRMWARE_FILENAME`, `FIRMWARE_URL`, `firmware_path(root) -> Path`, `ensure_firmware(path, opener=urllib.request.urlopen) -> Path`, `missing_tools() -> list[str]`, `erase_flash(port)`, `flash_firmware(port, image)`, `upload_firmware(port, root)`, `reset_board(port)`, `open_repl(port)`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_deploy.py`:

```python
import io
from pathlib import Path


def test_ensure_firmware_uses_cached_file(tmp_path):
    image = tmp_path / "fw.bin"
    image.write_bytes(b"cached")

    def opener(_url):
        raise AssertionError("should not download when cache exists")

    assert deploy.ensure_firmware(image, opener=opener) == image
    assert image.read_bytes() == b"cached"


def test_ensure_firmware_downloads_when_missing(tmp_path):
    image = tmp_path / "nested" / "fw.bin"

    class Response(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    assert deploy.ensure_firmware(image, opener=lambda _url: Response(b"downloaded")) == image
    assert image.read_bytes() == b"downloaded"


def test_missing_tools_reports_absent(monkeypatch):
    monkeypatch.setattr(deploy.shutil, "which", lambda name: None)
    assert deploy.missing_tools() == ["esptool", "mpremote"]


def test_upload_firmware_builds_expected_commands(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(deploy, "run", lambda cmd, check=True: calls.append(cmd))
    (tmp_path / "firmware" / "drivers").mkdir(parents=True)

    deploy.upload_firmware("/dev/ttyUSB0", tmp_path)

    flat = " ".join(" ".join(call) for call in calls)
    assert "boot.py" in flat
    assert "config.py" in flat
    assert "main.py" in flat
    assert "wifi_ap.py" in flat
    assert "webserver.py" in flat
    assert ":drivers" in flat
    assert "ina219.py" in flat
    assert "ssd1306.py" in flat


def test_flash_firmware_uses_expected_arguments(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(deploy, "run", lambda cmd, check=True: calls.append(cmd))
    image = tmp_path / "fw.bin"

    deploy.flash_firmware("/dev/ttyUSB0", image)

    assert calls == [[
        "esptool", "--chip", "esp32", "--port", "/dev/ttyUSB0",
        "--baud", "460800", "write_flash", "-z", "0x1000", str(image),
    ]]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_deploy.py -v`
Expected: FAIL with `AttributeError: module 'deploy' has no attribute 'ensure_firmware'`.

- [ ] **Step 3: Write minimal implementation**

Add to the top of `deploy.py`:

```python
import shutil
import subprocess
import urllib.request
from pathlib import Path
```

Add below the VID map:

```python
MICROPYTHON_VERSION = "v1.29.0"
FIRMWARE_FILENAME = "ESP32_GENERIC-20260824-v1.29.0.bin"
FIRMWARE_URL = f"https://micropython.org/resources/firmware/{FIRMWARE_FILENAME}"
FLASH_ADDRESS = "0x1000"
FLASH_BAUD = "460800"
FIRMWARE_FILES = ["boot.py", "config.py", "main.py", "wifi_ap.py", "webserver.py"]
DRIVER_FILES = ["ina219.py", "ssd1306.py"]
```

Add at the end of `deploy.py`:

```python
def firmware_path(root: Path) -> Path:
    return root / ".cache" / "micropython" / FIRMWARE_FILENAME


def ensure_firmware(path: Path, opener=urllib.request.urlopen) -> Path:
    if path.exists() and path.stat().st_size > 0:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {FIRMWARE_URL} ...")
    tmp = path.with_name(path.name + ".part")
    with opener(FIRMWARE_URL) as response, open(tmp, "wb") as out:
        shutil.copyfileobj(response, out)
    tmp.replace(path)
    return path


def missing_tools() -> list:
    return [tool for tool in ("esptool", "mpremote") if shutil.which(tool) is None]


def run(cmd, check=True):
    return subprocess.run(cmd, check=check)


def erase_flash(port: str) -> None:
    run(["esptool", "--chip", "esp32", "--port", port, "erase_flash"])


def flash_firmware(port: str, image: Path) -> None:
    run([
        "esptool", "--chip", "esp32", "--port", port,
        "--baud", FLASH_BAUD, "write_flash", "-z", FLASH_ADDRESS, str(image),
    ])


def upload_firmware(port: str, root: Path) -> None:
    firmware = root / "firmware"
    run(["mpremote", "connect", port, "fs", "mkdir", ":drivers"], check=False)
    for name in FIRMWARE_FILES:
        run(["mpremote", "connect", port, "fs", "cp", str(firmware / name), ":"])
    for name in DRIVER_FILES:
        run(["mpremote", "connect", port, "fs", "cp", str(firmware / "drivers" / name), ":drivers"])


def reset_board(port: str) -> None:
    run(["mpremote", "connect", port, "reset"], check=False)


def open_repl(port: str) -> None:
    run(["mpremote", "connect", port, "repl"], check=False)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_deploy.py -v`
Expected: 12 passed.

---

### Task 3: CLI wiring

**Files:**
- Modify: `deploy.py`
- Test: `tests/test_deploy.py`

**Interfaces:**
- Consumes: `scan_ports`, `select_port`, `is_esp_port`, `missing_tools`, `firmware_path`, `ensure_firmware`, `erase_flash`, `flash_firmware`, `upload_firmware`, `reset_board`, `open_repl`.
- Produces: `repo_root() -> Path`, `build_parser()`, `main(argv=None) -> int`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_deploy.py`:

```python
def test_main_list_with_no_ports(monkeypatch, capsys):
    monkeypatch.setattr(deploy, "missing_tools", lambda: [])
    monkeypatch.setattr(deploy, "scan_ports", lambda: [])
    assert deploy.main(["--list"]) == 0
    assert "No serial ports detected" in capsys.readouterr().out


def test_main_reports_missing_tools(monkeypatch, capsys):
    monkeypatch.setattr(deploy, "missing_tools", lambda: ["esptool"])
    assert deploy.main([]) == 1
    assert "esptool" in capsys.readouterr().out


def test_main_exits_when_no_ports_and_no_port_flag(monkeypatch, capsys):
    monkeypatch.setattr(deploy, "missing_tools", lambda: [])
    monkeypatch.setattr(deploy, "scan_ports", lambda: [])
    assert deploy.main([]) == 1
    assert "No serial ports detected" in capsys.readouterr().out


def test_main_uses_port_flag_and_runs_steps(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(deploy, "missing_tools", lambda: [])
    monkeypatch.setattr(deploy, "scan_ports", lambda: [])
    monkeypatch.setattr(deploy, "ensure_firmware", lambda path: calls.append("download"))
    monkeypatch.setattr(deploy, "erase_flash", lambda port: calls.append("erase"))
    monkeypatch.setattr(deploy, "flash_firmware", lambda port, image: calls.append("flash"))
    monkeypatch.setattr(deploy, "upload_firmware", lambda port, root: calls.append("upload"))
    monkeypatch.setattr(deploy, "reset_board", lambda port: calls.append("reset"))
    monkeypatch.setattr(deploy, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(deploy.time, "sleep", lambda _seconds: None)

    assert deploy.main(["--port", "/dev/ttyUSB0", "--yes", "--keep-files"]) == 0
    assert calls == ["download", "flash", "upload", "reset"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_deploy.py -v`
Expected: FAIL with `AttributeError: module 'deploy' has no attribute 'main'`.

- [ ] **Step 3: Write minimal implementation**

Add `import argparse`, `import sys`, and `import time` to the imports in `deploy.py`. Add at the end:

```python
def repo_root() -> Path:
    return Path(__file__).resolve().parent


def build_parser():
    parser = argparse.ArgumentParser(
        description="Flash MicroPython and deploy SolarLab Mini firmware to an ESP32."
    )
    parser.add_argument("--port", help="Serial port (skips scanning)")
    parser.add_argument("--list", action="store_true", dest="list_ports", help="List serial ports and exit")
    parser.add_argument("--keep-files", action="store_true", help="Skip erase_flash and keep existing files")
    parser.add_argument("--monitor", action="store_true", help="Open the MicroPython REPL after deployment")
    parser.add_argument("--yes", action="store_true", help="Do not ask for confirmation before erasing")
    return parser


def confirm(prompt: str, input_fn=input) -> bool:
    return input_fn(prompt).strip().lower() in ("y", "yes")


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)

    missing = missing_tools()
    if missing:
        print(f"Missing required tools: {', '.join(missing)}")
        print("Install with: pip install esptool mpremote")
        return 1

    if list_ports is None:
        print("pyserial is not installed. Install with: pip install pyserial")
        return 1

    ports = scan_ports()
    if args.list_ports:
        if not ports:
            print("No serial ports detected.")
            return 0
        print("Detected serial ports:")
        for index, port in enumerate(ports, start=1):
            print(f"  {index}. {format_port(port)}")
        return 0

    if args.port:
        port = args.port
    else:
        if not ports:
            print("No serial ports detected. Plug in the ESP32 with a data USB cable.")
            print("On Linux, ensure your user is in the 'dialout' group:")
            print("  sudo usermod -aG dialout $USER")
            return 1
        selected = select_port(ports)
        if selected is None:
            print("Cancelled.")
            return 0
        port = selected.device
        if not is_esp_port(selected):
            print(f"Warning: {port} does not look like a known ESP32 USB-serial adapter.")

    if not args.keep_files and not args.yes:
        if not confirm(f"Erase flash and install MicroPython {MICROPYTHON_VERSION} on {port}? [y/N] "):
            print("Cancelled.")
            return 0

    image = firmware_path(repo_root())
    try:
        ensure_firmware(image)
        if not args.keep_files:
            print(f"Erasing flash on {port} ...")
            erase_flash(port)
        print(f"Flashing MicroPython {MICROPYTHON_VERSION} ...")
        flash_firmware(port, image)
        print("Waiting for the board to reboot ...")
        time.sleep(2)
        print("Uploading firmware files ...")
        upload_firmware(port, repo_root())
        reset_board(port)
    except subprocess.CalledProcessError as exc:
        print(f"Command failed: {' '.join(map(str, exc.cmd))}")
        return 1
    except KeyboardInterrupt:
        print("\nInterrupted.")
        return 130
    except OSError as exc:
        print(f"Deployment failed: {exc}")
        return 1

    print("\nDone.")
    print("Join Wi-Fi: SolarLab-Mini (password: solarlab123)")
    print("Open: http://192.168.4.1/data")
    if args.monitor:
        open_repl(port)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_deploy.py -v`
Expected: 16 passed.

---

### Task 4: Make executable, document, ignore cache

**Files:**
- Modify: `.gitignore`
- Modify: `README.md`
- Modify: `deploy.py` (permissions)

**Interfaces:**
- Consumes: `deploy.py` CLI from Task 3.
- Produces: runnable `./deploy.py` and user-facing docs.

- [ ] **Step 1: Make the script executable**

Run: `chmod +x deploy.py`
Expected: no output; `test -x deploy.py` succeeds.

- [ ] **Step 2: Add cache to `.gitignore`**

Append:

```gitignore

# Deploy cache
.cache/
*.bin
```

- [ ] **Step 3: Add a README section**

Insert after the existing `## Firmware (MicroPython)` block in `README.md`:

```markdown
## Flash & deploy (MicroPython)

Requires Python 3 and the deploy tools:

```bash
pip install esptool mpremote
```

Connect the ESP32 with a **data** USB cable, then run:

```bash
./deploy.py
```

The CLI scans serial ports, marks known ESP32 adapters (`CP210x`, `CH340`,
`Espressif USB`, `FTDI`), and asks you to select one. It then erases the flash,
installs MicroPython v1.29.0, uploads `firmware/`, and resets the board.

Useful options:

```bash
./deploy.py --list        # only scan and print ports
./deploy.py --keep-files  # update files without erasing flash
./deploy.py --monitor     # open the REPL when done
./deploy.py --yes         # skip the erase confirmation
```

If no port appears on Linux, add your user to the serial group and log in again:

```bash
sudo usermod -aG dialout $USER
```
```

- [ ] **Step 4: Verify docs and script**

Run: `./deploy.py --help`
Expected: usage text including `--port`, `--list`, `--keep-files`, `--monitor`, `--yes`.

Run: `./deploy.py --list`
Expected: `No serial ports detected.` (no board connected).

---

### Task 5: Final verification

**Files:**
- No changes.

- [ ] **Step 1: Syntax check**

Run: `python3 -m py_compile deploy.py`
Expected: exit code 0.

- [ ] **Step 2: Full test suite**

Run: `python3 -m pytest tests/test_deploy.py -v`
Expected: 16 passed.

- [ ] **Step 3: Hardware-free CLI smoke test**

Run: `./deploy.py --list`
Expected: `No serial ports detected.` (or a port list if a board is connected).

- [ ] **Step 4: Report ready state**

Summarize for the user:
- What was added.
- Exact command to run tomorrow: `./deploy.py`
- That full flashing still needs the ESP32 physically connected.
