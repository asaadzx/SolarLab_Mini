# Team Knowledge — SolarLab Mini

This folder is the onboarding guide for anyone joining the project. The Markdown
file is the source of truth; `Team Knowledge.docx` is generated from it by
`generate_docx.py` so you can hand a printed/Word copy to a teammate.

## What this project does

SolarLab Mini measures a small solar panel with an ESP32. The ESP32 creates its own
Wi-Fi network, shows voltage/current/power on a small OLED, and serves the same
numbers as JSON. A laptop dashboard can display them live and a logger can save
them to CSV. The MicroPython code in `firmware/` is the working implementation.

## What each component does

| Component | What it does |
|---|---|
| ESP32-WROOM32 DevKit | Runs MicroPython, reads I2C, hosts Wi-Fi AP `SolarLab-Mini`, serves JSON at `192.168.4.1/data`, and drives the OLED. |
| SSD1306 OLED (0.96", 128x64) | Shows `V`, `I`, and `P` locally. Address `0x3C`, on I2C bus 0. |
| INA219 sensor | Measures bus voltage and the tiny voltage across its internal 0.1 Ω shunt, from which current and power are calculated. Address `0x40`, on I2C bus 1. |
| Solar panel | The power source being measured. Keep its open-circuit voltage below 26 V. |
| Inline fuse | Protects the panel and wiring from overcurrent; always placed in series on the panel's positive wire. |
| DC load / resistor / bulb | Gives the panel somewhere to send power so current can be measured. A motor is not a good first load because it stalls and collapses the panel voltage. |
| Battery + charge controller | If storing energy, the battery must go through a controller matched to its chemistry (e.g. TP4056 for one Li-ion cell). Never wire a battery directly to the sensor or ESP32. |
| USB cable | Powers and programs the ESP32 during development; provides the serial console for debugging. |
| `deploy.py` | Installs MicroPython, uploads `firmware/`, and resets the board. |
| MicroPython firmware | `main.py` (loop), `config.py` (pins), `wifi_ap.py` (AP), `webserver.py` (JSON), and the two drivers. |
| Flask dashboard | Browser page at `127.0.0.1:5000` that polls `/api/latest`, which proxies the ESP32's `/data`, plus a capture date/solar angle form, a day picker, three charts (voltage, current, power), a CSV download button, and a recent-events panel. |
| Dashboard storage | While the dashboard is open, a background poller saves readings to `laptop_app/dashboard/data/solarlab.sqlite3` and writes rotating events/errors to `laptop_app/dashboard/data/app.log`. Routes: `/api/readings`, `/api/days`, `/api/metadata`, `/api/logs`, `/export.csv`. |
| CSV logger | `receiver_http.py` polls `/data` once per second and appends timestamped rows to `data/exports/`. |

## Wiring summary

### Power loop (build this first)

```
Panel (+) ── Fuse ── INA219 VIN+ ──[0.1 Ω shunt inside module]── VIN− ── Load (+) ── Load (−) ── Panel (−)
```

### Common ground node

These four points must be the same node:

```
Panel (−) ── Load (−) ── INA219 GND ── ESP32 GND
```

### I2C signals

```
OLED:   VCC -> 3V3   GND -> GND   SDA -> GPIO23   SCL -> GPIO21   (I2C0, addr 0x3C)
INA219: VCC -> 3V3   GND -> GND   SDA -> GPIO19   SCL -> GPIO18   (I2C1, addr 0x40)
```

The two devices are on **different I2C buses**; do not swap the pin pairs.

## Project structure

| Folder / file | Purpose |
|---|---|
| `firmware/` | MicroPython code that runs on the ESP32. |
| `firmware/drivers/` | Minimal `ina219.py` and `ssd1306.py` drivers. |
| `laptop_app/` | Host-side scripts (CSV logger, requirements). |
| `laptop_app/dashboard/` | Flask app that proxies sensor data for the browser. |
| `laptop_app/dashboard/templates/` | `index.html` dashboard page with three Chart.js graphs. |
| `laptop_app/dashboard/static/` | Dashboard stylesheet. |
| `laptop_app/dashboard/data/` | Generated at runtime: `solarlab.sqlite3` readings and rotating `app.log`. |
| `docs/` | Wiring guide and design documents. |
| `docs/superpowers/specs/` | Design specs describing why changes were made. |
| `docs/superpowers/plans/` | Step-by-step implementation plans. |
| `tests/` | Host-side pytest suite; runs without the board. |
| `team knowledge/` | This onboarding guide in Markdown and Word formats. |
| `deploy.py` | Flash and deploy CLI for the ESP32. |
| `src/`, `include/`, `firmware_pio/`, `test_wifi/`, `platformio.ini` | Older Arduino/PlatformIO experiments; not the active firmware. |
| `.cache/` | Downloaded MicroPython firmware image (ignored by git). |

## Quick start

1. Install tools: `pip install esptool mpremote pyserial`.
2. Connect the ESP32 with a data USB cable and run `./deploy.py`.
3. Join Wi-Fi `SolarLab-Mini` (password `solarlab123`) on your laptop or phone.
4. Open `http://192.168.4.1/data` to see JSON, or check the OLED.
5. On the laptop, run `python dashboard/app.py` from `laptop_app/` and open
   `http://127.0.0.1:5000` for the live dashboard. While the page is open, readings
   are stored in `laptop_app/dashboard/data/solarlab.sqlite3` and events/errors in
   the rotating `laptop_app/dashboard/data/app.log`.
6. Set the capture date and solar angle in the form: this metadata tags future
   readings only. Use the day picker to view the voltage, current, and power charts
   for a stored day.
7. Use the CSV download button to export the selected day's readings, and the
   recent-events panel to see the latest log lines. Docker packaging is planned as
   phase 2, so run the app directly with Python for now.
8. Run `python -m pytest tests/ -q` from the repository root to check the code.

## Safety

- Always use a correctly rated DC fuse in series on the panel's positive wire.
- Common ground is mandatory: panel −, load −, INA219 GND, and ESP32 GND.
- Keep panel voltage below 26 V and load current below 3.2 A.
- Never connect the panel or a battery to ESP32 3V3 or GPIO pins.
- Batteries require a charge controller matched to their chemistry.
- Disconnect USB and panel before changing wiring; verify voltages with a multimeter.

## Troubleshooting

| Symptom | Likely cause / check |
|---|---|
| No `SolarLab-Mini` network | Firmware crashed before AP start; open the serial console. OLED init is non-fatal now, so check boot messages. |
| `bus_v` near 0 V while panel is lit | Missing common ground, blown fuse, or panel + not on VIN+. With no load, VIN− should still show the panel voltage through the shunt. |
| I2C scan shows no `0x3C` / `0x40` | Wrong pins or wiring. OLED = 23/21, INA219 = 19/18. |
| Serial permission denied on Linux | Re-run `sudo chmod 666 /dev/ttyUSB0`, or add your user to `dialout`/`uucp` and log in again. |
| Dashboard shows an error | Laptop is not joined to the ESP32 AP, or the board is powered off. |
| Current reads 0 with a load | A wire bridges VIN+ to VIN− (bypasses the shunt) or the load is not connected to VIN−. |
