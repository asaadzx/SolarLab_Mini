#!/usr/bin/env python3
"""SolarLab Mini ESP32 MicroPython deploy CLI."""

from __future__ import annotations  # Delay annotation evaluation for compatibility

import argparse  # Parse command-line flags
import shutil  # Locate tools and copy downloaded firmware
import subprocess  # Run esptool and mpremote as child processes
import sys  # Exit with a status code
import time  # Wait for the board to reboot after flashing
import urllib.request  # Download the MicroPython firmware image
from pathlib import Path  # Work with filesystem paths

try:
    from serial.tools import list_ports  # pyserial's serial-port discovery
except ImportError:  # pragma: no cover - handled at runtime
    list_ports = None  # Missing pyserial is reported in main()

ESP_VIDS = {  # USB vendor IDs of common ESP32 USB-serial adapters
    0x10C4: "CP210x",  # Silicon Labs CP210x
    0x1A86: "CH340/CH9102",  # WCH CH340 and CH9102
    0x303A: "Espressif USB",  # Native Espressif USB-JTAG
    0x0403: "FTDI",  # FTDI FT232 and friends
}

MICROPYTHON_VERSION = "v1.29.0"  # Firmware version installed by this script
FIRMWARE_FILENAME = "ESP32_GENERIC-20260824-v1.29.0.bin"  # Image file name
FIRMWARE_URL = f"https://micropython.org/resources/firmware/{FIRMWARE_FILENAME}"  # Download URL
FLASH_ADDRESS = "0x1000"  # Flash offset required by ESP32 MicroPython images
FLASH_BAUD = "460800"  # Fast flashing baud rate
FIRMWARE_FILES = ["boot.py", "config.py", "main.py", "wifi_ap.py", "webserver.py"]  # Top-level board files
DRIVER_FILES = ["ina219.py", "ssd1306.py"]  # Files copied into :drivers on the board


def is_esp_port(port) -> bool:
    """Return True when a serial port has a known ESP32 adapter vendor ID."""
    return port.vid in ESP_VIDS  # port.vid is the USB vendor ID


def format_port(port) -> str:
    """Format one serial port as a single human-readable table row."""
    if port.vid is None or port.pid is None:  # No USB IDs available
        vid_pid = "----:----"  # Placeholder for unknown IDs
    else:
        vid_pid = f"{port.vid:04X}:{port.pid:04X}"  # Hex vendor:product IDs
    marker = "yes" if is_esp_port(port) else "no"  # Whether it looks like an ESP32
    return f"{port.device:<20} {port.description:<35} {vid_pid:<10} ESP: {marker}"  # Row text


def scan_ports() -> list:
    """Return detected serial ports, filtering out unusable built-in UARTs."""
    if list_ports is None:  # pyserial not installed
        return []  # No ports can be discovered
    ports = list(list_ports.comports())  # All ports reported by pyserial
    return [
        port for port in ports  # port is one discovered serial device
        if not (port.device.startswith("/dev/ttyS") and port.vid is None)  # Skip onboard UARTs
    ]


def select_port(ports, input_fn=input, print_fn=print):
    """Prompt the user to choose one port from the list; return None to quit."""
    print_fn("Detected serial ports:")  # Table header
    for index, port in enumerate(ports, start=1):  # index: 1-based menu number
        print_fn(f"  {index}. {format_port(port)}")  # One menu row
    while True:  # Keep asking until a valid choice or quit
        choice = input_fn(f"Select ESP32 [1-{len(ports)}] (q to quit): ").strip()  # User input
        if choice.lower() == "q":  # Quit request
            return None  # Cancelled
        if choice.isdigit() and 1 <= int(choice) <= len(ports):  # Valid menu number
            return ports[int(choice) - 1]  # Convert back to zero-based index
        print_fn("Invalid selection.")  # Try again


def firmware_path(root: Path) -> Path:
    """Return the local cache path for the MicroPython firmware image."""
    return root / ".cache" / "micropython" / FIRMWARE_FILENAME  # Cached image location


def ensure_firmware(path: Path, opener=urllib.request.urlopen) -> Path:
    """Download the firmware to a temporary file if it is not cached yet."""
    if path.exists() and path.stat().st_size > 0:  # A usable cached copy exists
        return path  # Nothing to download
    path.parent.mkdir(parents=True, exist_ok=True)  # Create cache directories
    print(f"Downloading {FIRMWARE_URL} ...")  # Progress message
    tmp = path.with_name(path.name + ".part")  # Partial download file
    with opener(FIRMWARE_URL) as response, open(tmp, "wb") as out:  # response: URL stream, out: local file
        shutil.copyfileobj(response, out)  # Stream the download to disk
    tmp.replace(path)  # Atomically move the complete file into place
    return path  # Path to the ready-to-flash image


def missing_tools() -> list:
    """Return the names of required command-line tools that are not installed."""
    return [tool for tool in ("esptool", "mpremote") if shutil.which(tool) is None]  # tool is a command name


def run(cmd, check=True):
    """Run a subprocess command, raising on failure unless check is False."""
    return subprocess.run(cmd, check=check)  # cmd is the argument list


def erase_flash(port: str) -> None:
    """Erase the entire flash memory of the ESP32 on the given port."""
    run(["esptool", "--chip", "esp32", "--port", port, "erase_flash"])  # Destructive erase


def flash_firmware(port: str, image: Path) -> None:
    """Write the MicroPython firmware image at the required flash address."""
    run([
        "esptool", "--chip", "esp32", "--port", port,
        "--baud", FLASH_BAUD, "write_flash", "-z", FLASH_ADDRESS, str(image),
    ])  # -z compresses the transfer


def upload_firmware(port: str, root: Path) -> None:
    """Copy the firmware Python files onto the board's filesystem."""
    firmware = root / "firmware"  # Local source directory
    run(["mpremote", "connect", port, "fs", "mkdir", ":drivers"], check=False)  # Ignore if it exists
    for name in FIRMWARE_FILES:  # name is a top-level firmware file
        run(["mpremote", "connect", port, "fs", "cp", str(firmware / name), ":"])  # Copy to board root
    for name in DRIVER_FILES:  # name is a driver file
        run(["mpremote", "connect", port, "fs", "cp", str(firmware / "drivers" / name), ":drivers"])  # Copy to :drivers


def reset_board(port: str) -> None:
    """Reset the board so the newly uploaded files start running."""
    run(["mpremote", "connect", port, "reset"], check=False)  # Ignore reset transport errors


def open_repl(port: str) -> None:
    """Open an interactive MicroPython REPL on the board."""
    run(["mpremote", "connect", port, "repl"], check=False)  # Blocks until the user exits


def repo_root() -> Path:
    """Return the repository root directory containing this script."""
    return Path(__file__).resolve().parent  # Directory of deploy.py


def build_parser():
    """Create and return the command-line argument parser."""
    parser = argparse.ArgumentParser(  # parser collects the flags below
        description="Flash MicroPython and deploy SolarLab Mini firmware to an ESP32."
    )
    parser.add_argument("--port", help="Serial port (skips scanning)")  # Explicit port
    parser.add_argument("--list", action="store_true", dest="list_ports", help="List serial ports and exit")  # List only
    parser.add_argument("--keep-files", action="store_true", help="Skip erase_flash and keep existing files")  # Keep files
    parser.add_argument("--monitor", action="store_true", help="Open the MicroPython REPL after deployment")  # Open REPL
    parser.add_argument("--yes", action="store_true", help="Do not ask for confirmation before erasing")  # Skip prompt
    return parser  # Configured parser


def confirm(prompt: str, input_fn=input) -> bool:
    """Return True when the user answers y or yes to the given prompt."""
    return input_fn(prompt).strip().lower() in ("y", "yes")  # Normalize the answer


def main(argv=None) -> int:
    """Run the deploy workflow and return a process exit code."""
    args = build_parser().parse_args(argv)  # Parsed command-line flags
    missing = missing_tools()  # Required tools that are absent
    if missing:  # Cannot continue without esptool/mpremote
        print(f"Missing required tools: {', '.join(missing)}")  # List them
        print("Install with: pip install esptool mpremote")  # Installation hint
        return 1  # Failure exit code
    if list_ports is None:  # pyserial missing
        print("pyserial is not installed. Install with: pip install pyserial")  # Installation hint
        return 1  # Failure exit code

    ports = scan_ports()  # Detected serial devices
    if args.list_ports:  # --list flag
        if not ports:  # Nothing detected
            print("No serial ports detected.")  # Message
            return 0  # Clean exit
        print("Detected serial ports:")  # Header
        for index, port in enumerate(ports, start=1):  # index: 1-based row number
            print(f"  {index}. {format_port(port)}")  # Row text
        return 0  # Clean exit

    if args.port:  # --port provided
        port = args.port  # Use the explicit device path
    else:
        if not ports:  # No devices found
            print("No serial ports detected. Plug in the ESP32 with a data USB cable.")  # Hint
            print("On Linux, ensure your user is in the 'dialout' group:")  # Hint
            print("  sudo usermod -aG dialout $USER")  # Command
            return 1  # Failure exit code
        selected = select_port(ports)  # User's chosen port object
        if selected is None:  # User quit
            print("Cancelled.")  # Message
            return 0  # Clean exit
        port = selected.device  # Device path of the chosen port
        if not is_esp_port(selected):  # Unknown adapter
            print(f"Warning: {port} does not look like a known ESP32 USB-serial adapter.")  # Warning

    if not args.keep_files and not args.yes:  # Destructive step needs a confirmation
        if not confirm(f"Erase flash and install MicroPython {MICROPYTHON_VERSION} on {port}? [y/N] "):
            print("Cancelled.")  # User declined
            return 0  # Clean exit

    image = firmware_path(repo_root())  # Local cached image path
    try:
        ensure_firmware(image)  # Download if needed
        if not args.keep_files:  # --keep-files preserves the old flash contents
            print(f"Erasing flash on {port} ...")  # Progress message
            erase_flash(port)  # Erase first
        print(f"Flashing MicroPython {MICROPYTHON_VERSION} ...")  # Progress message
        flash_firmware(port, image)  # Write the image
        print("Waiting for the board to reboot ...")  # Progress message
        time.sleep(2)  # Give the board time to restart
        print("Uploading firmware files ...")  # Progress message
        upload_firmware(port, repo_root())  # Copy Python files
        reset_board(port)  # Restart into the new firmware
    except subprocess.CalledProcessError as exc:  # exc holds the failed command
        print("Command failed: " + " ".join(map(str, exc.cmd)))  # Show the command
        return 1  # Failure exit code
    except KeyboardInterrupt:  # User pressed Ctrl+C
        print("\nInterrupted.")  # Message
        return 130  # Conventional Ctrl+C exit code
    except OSError as exc:  # exc is the filesystem or serial error
        print(f"Deployment failed: {exc}")  # Message
        return 1  # Failure exit code

    print("\nDone.")  # Success message
    print("Join Wi-Fi: SolarLab-Mini (password: solarlab123)")  # Next step
    print("Open: http://192.168.4.1/data")  # Next step
    if args.monitor:  # --monitor flag
        open_repl(port)  # Open the REPL
    return 0  # Success exit code


if __name__ == "__main__":  # Only run when invoked as a script
    sys.exit(main())  # Exit with the returned status code
