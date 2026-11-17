# SolarLab Mini

Low-cost solar panel monitoring system: an ESP32 reads a solar panel's voltage and
current with an INA219, shows the values on an OLED, and serves them as JSON over
its own Wi-Fi access point. A small Flask dashboard on a laptop can plot them live.

**The active implementation is the MicroPython firmware in `firmware/`.** The
PlatformIO/Arduino folders (`src/`, `include/`, `firmware_pio/`, `test_wifi/`) are
earlier experiments kept for reference.

## Hardware

- ESP32-WROOM-32 DevKit (MicroPython v1.29.0)
- INA219 current/voltage sensor, I2C address `0x40`
- 0.96" SSD1306 OLED, I2C address `0x3C`
- Small solar panel (keep open-circuit voltage below 26 V)
- Inline DC fuse on the panel's positive wire
- USB cable to power the ESP32 during development

### Verified wiring (two separate I2C buses)

| Signal | OLED (SSD1306) | INA219 |
|---|---|---|
| VCC | 3V3 | 3V3 |
| GND | common ground | common ground |
| SDA | GPIO23 | GPIO19 |
| SCL | GPIO21 | GPIO18 |
| I2C bus | I2C(0) | I2C(1) |

Power loop and common-ground details are in [docs/wiring.md](docs/wiring.md).

## Flash and deploy

Requires Python 3, `esptool`, `mpremote`, and `pyserial`:

```bash
pip install esptool mpremote pyserial
./deploy.py
```

The CLI scans serial ports, highlights known ESP32 adapters, asks which one to use,
erases the flash, installs MicroPython, uploads `firmware/`, and resets the board.

```bash
./deploy.py --list         # list serial ports only
./deploy.py --keep-files   # update files without erasing
./deploy.py --port /dev/ttyUSB0 --yes
./deploy.py --monitor      # open the REPL after deploying
```

On Linux, if your user cannot open the serial port, add yourself to the serial group
and log in again (the group may be `dialout` or `uucp` depending on the adapter):

```bash
sudo usermod -aG dialout $USER
```

## Wi-Fi and data

After boot the ESP32 creates:

- SSID: `SolarLab-Mini`
- Password: `solarlab123`
- JSON endpoint: `http://192.168.4.1/data`

Example response:

```json
{"voltage": 4.536, "current": 0.125, "power": 0.567, "timestamp": 1234}
```

Join this network on the laptop (or open the URL on a phone) to reach the board.
The laptop will not have internet access while joined to the ESP32 AP.

## Laptop app

```bash
cd laptop_app
pip install -r requirements.txt

# Live dashboard (http://127.0.0.1:5000)
python dashboard/app.py

# CSV logger -> data/exports/solarlab_<timestamp>.csv
python receiver_http.py
```

Both scripts read `http://192.168.4.1/data`, so the laptop must be on the
`SolarLab-Mini` network.

While the dashboard is open, it logs readings to
`laptop_app/dashboard/data/solarlab.sqlite3` and writes rotating events/errors to
`laptop_app/dashboard/data/app.log`. The page has a capture date/solar angle form,
a day picker, three charts (voltage, current, power), a CSV download button, and a
recent-events panel. The form tags future readings; CSV export is filtered by the
selected day.

| Route | Purpose |
|---|---|
| `/api/latest` | Live proxy of the ESP32's current reading (no storage). |
| `/api/readings` | Stored readings for the selected day. |
| `/api/days` | Available capture days for the day picker. |
| `/api/metadata` | POST the capture date and solar angle for future readings. |
| `/api/logs` | Recent log lines for the recent-events panel. |
| `/export.csv` | Download the selected day's readings as CSV. |

## Docker (host networking)

The dashboard can run as a minimal container. The laptop must be joined to
`SolarLab-Mini` so the container can reach `192.168.4.1/data` through host
networking; there is no `ports:` mapping.

```bash
docker compose build
docker compose up -d
# Open http://127.0.0.1:5000
docker compose logs -f dashboard
docker compose down
```

SQLite and rotating logs live in the `solarlab-data` named volume at
`/app/data`. `docker compose down` preserves it. To back it up:

```bash
docker run --rm -v solarlab-data:/data -v "$PWD":/backup alpine \
  tar czf /backup/solarlab-data-backup.tgz -C /data .
```

For testing without the board, set `ESP_URL` before `docker compose up`, for
example `ESP_URL=http://127.0.0.1:18765/data docker compose up -d`.

## Tests

```bash
python -m pytest tests/ -q
```

Covers the deploy CLI, INA219 register scaling, webserver socket behavior, and the
dashboard routes (dashboard tests need Flask installed).

## Safety

- Always put a correctly rated DC fuse in series on the panel's positive wire.
- Panel (−), load (−), INA219 GND, and ESP32 GND must share one common ground.
- Never feed the panel into the ESP32's 3V3 pin or a GPIO.
- Keep panel voltage below 26 V and load current below 3.2 A (INA219 shunt limit).
- A battery needs a chemistry-matched charge controller; never connect it directly.
- Small motors draw far more than a small panel can supply and collapse the voltage.

A beginner-friendly onboarding guide is in [`team knowledge/README.md`](team%20knowledge/README.md).
