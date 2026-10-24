# SolarLab Mini - Design Spec (2026-10-24)

## Goal
Build a low-cost, plug-and-play solar panel research monitor using ESP32-WROOM (instead of ESP32-S3), INA219 current/voltage sensor, 0.96" SSD1306 OLED, with a laptop dashboard for logging and export. Start with MicroPython on ESP32 creating its own Wi-Fi AP, and a Python laptop app to log/visualize data.

## Hardware
- ESP32-WROOM-32 DevKit
- INA219 I2C Current/Voltage Sensor Module
- 0.96" OLED SSD1306 I2C
- 10W 18V Solar Panel
- Inline fuse holder + 1A/2A fast-blow fuse
- XT60 or DC barrel jack / screw terminals
- Breadboard, jumper wires, silicone wire
- Project enclosure (later)
- Multimeter (for calibration)

## Architecture
1. Solar panel (+) fused -> INA219 VIN+; panel (-) and INA219 VIN- to common GND; INA219 I2C to ESP32
2. ESP32 runs MicroPython: reads INA219, updates OLED, hosts Wi-Fi AP + HTTP JSON endpoint
3. Laptop connects to ESP32 AP, polls HTTP endpoint, logs to SQLite/CSV, serves local dashboard

## Firmware (MicroPython)
Files in `firmware/`:
- `boot.py` - minimal boot
- `config.py` - AP config, I2C pins (e.g. SDA=21, SCL=22), calibration
- `wifi_ap.py` - start AP
- `webserver.py` - simple HTTP server serving JSON at `/data`
- `main.py` - loop: read sensors, update display, handle requests
- `drivers/ina219.py`, `drivers/ssd1306.py` - drivers

I2C bus shared by INA219 and OLED.

## Laptop App
Files in `laptop_app/`:
- `receiver_http.py` - poll ESP32 HTTP endpoint
- `storage/database.py`, `storage/csv_export.py`
- `dashboard/app.py` (Flask) - local web UI
- `requirements.txt` - flask, requests, pandas (optional)

## Safety
- Fuse on panel positive before sensor
- Common ground
- Power ESP32 via USB during testing (do not power from panel)
- Verify with multimeter before connecting
- Start with short outdoor tests

## Tomorrow's Plan
See implementation checklist below.

## Implementation Checklist
- [ ] Inventory parts, identify panel Voc with multimeter
- [ ] Setup MicroPython on ESP32-WROOM (esptool/Thonny/ampy)
- [ ] I2C scan, connect INA219+OLED
- [ ] Write minimal firmware to read INA219 and show on OLED
- [ ] Add Wi-Fi AP + HTTP JSON endpoint
- [ ] Add fuse and test with 18V panel outdoors (short test)
- [ ] Laptop HTTP receiver + CSV logging
- [ ] Minimal Flask dashboard (live values)
- [ ] Document wiring and first dataset
- [ ] Init git repo and push to GitHub

## GitHub "Plug and Play" Goal
Make repo cloneable: include README with wiring, MicroPython setup, laptop setup, and example config. Add requirements.txt and clear instructions.
