#!/usr/bin/env python3
"""SolarLab Mini ESP32 MicroPython deploy CLI."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

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

MICROPYTHON_VERSION = "v1.29.0"
FIRMWARE_FILENAME = "ESP32_GENERIC-20260824-v1.29.0.bin"
FIRMWARE_URL = f"https://micropython.org/resources/firmware/{FIRMWARE_FILENAME}"
FLASH_ADDRESS = "0x1000"
FLASH_BAUD = "460800"
FIRMWARE_FILES = ["boot.py", "config.py", "main.py", "wifi_ap.py", "webserver.py"]
DRIVER_FILES = ["ina219.py", "ssd1306.py"]


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
    ports = list(list_ports.comports())
    return [
        port for port in ports
        if not (port.device.startswith("/dev/ttyS") and port.vid is None)
    ]


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
        print("Command failed: " + " ".join(map(str, exc.cmd)))
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
