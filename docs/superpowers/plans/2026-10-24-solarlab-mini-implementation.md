# SolarLab Mini - Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Get a working breadboard prototype: ESP32-WROOM runs MicroPython, reads INA219, shows on OLED, hosts Wi-Fi AP with HTTP JSON endpoint. Laptop polls and logs to CSV.

**Architecture:** Solar panel -> fused high-side to INA219, common GND, I2C to ESP32 (SDA=21/SCL=22). ESP32 AP + simple HTTP server. Laptop HTTP poller + CSV/SQLite.

**Tech Stack:** MicroPython (ESP32), Arduino-style libs or custom drivers, Python 3 (requests, flask), SQLite

---

## Task 1: Create firmware structure and config

**Files:**
- Create: `firmware/config.py`
- Create: `firmware/wifi_ap.py`
- Create: `firmware/drivers/ssd1306.py`
- Create: `firmware/drivers/ina219.py` (placeholder or use simple impl)

**Steps:**
- [ ] 1.1 Write config.py with AP name, password, I2C pins, addresses
- [ ] 1.2 Write wifi_ap.py to start AP
- [ ] 1.3 Add minimal ssd1306 driver (I2C) - can use common MicroPython version or simple
- [ ] 1.4 Add basic ina219 reading helper or notes

```python
# firmware/config.py
AP_SSID = "SolarLab-Mini"
AP_PASSWORD = "solarlab123"
I2C_SDA = 21
I2C_SCL = 22
INA219_ADDR = 0x40
OLED_ADDR = 0x3C
```

```python
# firmware/wifi_ap.py
import network
from config import AP_SSID, AP_PASSWORD

def start_ap():
    ap = network.WLAN(network.AP_IF)
    ap.active(True)
    ap.config(essid=AP_SSID, password=AP_PASSWORD)
    return ap
```

Commit: `git add firmware/ && git commit -m "feat: add firmware structure and AP config"`

---

## Task 2: Web server and main loop

**Files:**
- Create: `firmware/webserver.py`
- Create: `firmware/boot.py`
- Create: `firmware/main.py`

**Steps:**
- [ ] 2.1 Simple socket server to serve JSON at /data
- [ ] 2.2 boot.py starts AP and main
- [ ] 2.3 main.py reads sensors (dummy first), updates OLED, handles requests

Keep it minimal for first test.

Commit: `git add firmware/boot.py firmware/main.py firmware/webserver.py && git commit -m "feat: add webserver and main loop"`

---

## Task 3: Laptop HTTP receiver and CSV logging

**Files:**
- Create: `laptop_app/requirements.txt`
- Create: `laptop_app/receiver_http.py`
- Create: `laptop_app/storage/csv_export.py`
- Create: `data/.gitkeep`

**Steps:**
- [ ] 3.1 requirements.txt with requests
- [ ] 3.2 receiver_http.py polls http://192.168.4.1/data every second, writes to CSV with timestamp
- [ ] 3.3 Test logic (can mock)

Commit: `git add laptop_app/ data/ && git commit -m "feat: add laptop HTTP receiver and CSV logging"`

---

## Task 4: Minimal Flask dashboard

**Files:**
- Create: `laptop_app/dashboard/app.py`
- Create: `laptop_app/dashboard/templates/index.html`
- Create: `laptop_app/dashboard/static/style.css`

**Steps:**
- [ ] 4.1 Flask app serves page, fetches from ESP32 or shows latest from file
- [ ] 4.2 Simple HTML with live values and chart placeholder

Commit: `git add laptop_app/dashboard/ && git commit -m "feat: add minimal Flask dashboard"`

---

## Task 5: Docs and wiring guide

**Files:**
- Create: `docs/wiring.md`
- Create: `README.md`

**Steps:**
- [ ] 5.1 Document I2C wiring, fuse placement, safety
- [ ] 5.2 README with setup instructions (MicroPython, Thonny/esptool, laptop)
- [ ] 5.3 Include notes about 18V panel and ESP32-WROOM

Commit: `git add docs/ README.md && git commit -m "docs: add wiring guide and README"`

---

## Execution
Start with Task 1. Do breadboard wiring in parallel conceptually, but implement files first so ready to test tomorrow.
