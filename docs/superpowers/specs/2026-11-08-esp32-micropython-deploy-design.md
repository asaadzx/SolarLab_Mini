# ESP32 MicroPython Deploy CLI - Design Spec (2026-11-08)

## Goal
Provide a one-command, interactive CLI that prepares a bare ESP32-WROOM for
SolarLab Mini: scan serial ports, let the user pick the board, flash a pinned
MicroPython image, and upload the existing `firmware/` files. The board is not
connected during development, so everything must be ready to run the moment it
is plugged in.

## Scope
In scope:
- New executable `deploy.py` at the repository root (Python 3, stdlib + pyserial).
- Interactive numbered port menu with an explicit non-interactive mode.
- README instructions for installing tools and running the CLI.
- `.gitignore` entries for the downloaded firmware cache.

Out of scope:
- Changes to MicroPython firmware behavior or drivers.
- Laptop app changes.
- Windows-specific handling beyond normal pyserial behavior.

## Pinned Firmware
- MicroPython v1.29.0, ESP32_GENERIC (4 MiB flash).
- URL: `https://micropython.org/resources/firmware/ESP32_GENERIC-20260824-v1.29.0.bin`
- Cached at `.cache/micropython/ESP32_GENERIC-20260824-v1.29.0.bin`.
- Downloaded with `urllib` only when the cached file is missing.

## Dependencies
- `pyserial` (port scanning), `esptool` (erase/flash), `mpremote` (file upload,
  REPL). All three are already installed in the current environment; README
  documents `pip install esptool mpremote` (pyserial comes with esptool).
- The script checks for the `esptool` and `mpremote` executables at startup and
  exits with install guidance if missing.

## CLI Interface
```
./deploy.py [options]

Options:
  --port PORT        Skip scanning and use this serial port
  --list             Scan and print ports, then exit
  --keep-files       Skip erase_flash and keep files already on the board
  --monitor          Open the MicroPython REPL after deployment
  --yes              Do not ask for confirmation before erasing
  -h, --help         Show usage
```

### Interactive flow
1. Print a short banner with the target MicroPython version.
2. Scan ports with `serial.tools.list_ports.comports()`.
3. Print a numbered table: index, port, description, VID:PID, and an
   `ESP?` marker for known ESP32 USB-serial bridges.
4. Prompt `Select ESP32 [1-N]:`; re-prompt on invalid input; `q` quits.
5. If the chosen port is not a known ESP bridge, print a warning and continue.
6. If `--keep-files` is not set and `--yes` is not set, ask
   `Erase flash and install MicroPython v1.29.0? [y/N]`.
7. Download the image if needed, erase (unless `--keep-files`), flash at
   `0x1000` with baud `460800`, upload firmware, reset.
8. Print next steps: join Wi-Fi AP `SolarLab-Mini` (password `solarlab123`),
   open `http://192.168.4.1/data`.
9. With `--monitor`, start `mpremote connect <port> repl`.

### Port classification
Known ESP32 USB-serial vendor IDs:
- `0x10C4` Silicon Labs CP210x
- `0x1A86` QinHeng CH340/CH9102
- `0x303A` Espressif native USB
- `0x0403` FTDI

These are marked `yes`; everything else is marked `no` but still selectable.

## Upload Behavior
- Upload `boot.py`, `config.py`, `main.py`, `wifi_ap.py`, `webserver.py` to `/`.
- Upload `drivers/ina219.py` and `drivers/ssd1306.py` to `/drivers`.
- Skip `__pycache__` and `*.pyc`.
- Uses `mpremote connect <port> fs cp ...` and `mpremote reset`.

## Error Handling
- Clear non-zero exits for: missing tools, no serial ports, invalid selection,
  failed download, failed flash, failed upload.
- Ctrl-C exits cleanly with a message.
- `--keep-files` skips only the erase step; flashing and upload still run.

## Verification
- `python3 -m py_compile deploy.py` passes.
- `./deploy.py --help` prints usage without touching hardware.
- `./deploy.py --list` runs on a machine with no board and reports no ports.
- Port-classification logic is covered by small unit tests.
- Full hardware verification happens when the ESP32 is connected.

## Known Firmware Issues (not fixed here)
- `firmware/drivers/ina219.py` never writes the calibration register and its
  current calculation is off by roughly 1000x.
- `firmware/boot.py` imports `main`, so `main.py` does not run through the
  normal boot path.
These are uploaded as-is and should be addressed in a follow-up.
