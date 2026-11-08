# SolarLab Mini

Low-cost plug-and-play solar panel monitoring system using ESP32-WROOM, INA219, and SSD1306 OLED.

## Hardware
- ESP32-WROOM-32 DevKit
- INA219 Current/Voltage Sensor (I2C 0x40)
- 0.96" SSD1306 OLED (I2C 0x3C)
- 10W 18V Solar Panel
- Inline fuse (1A/2A) on panel +
- Breadboard, wires, multimeter

## Firmware (MicroPython)
1. Flash MicroPython to ESP32-WROOM
2. Upload `firmware/` contents to ESP32 (e.g., with Thonny or ampy)
3. Power via USB, ESP32 creates AP `SolarLab-Mini` (password `solarlab123`)
4. Connect to AP, visit `http://192.168.4.1` or poll `/data` for JSON

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

## Wiring (I2C)
- VCC: 3.3V
- GND: common
- SDA: GPIO21
- SCL: GPIO22
- Solar panel + through fuse to INA219 VIN+, - to GND

## Laptop App
```bash
cd laptop_app
pip install -r requirements.txt
# Log data
python receiver_http.py
# Dashboard
cd dashboard
python app.py
# Open http://127.0.0.1:5000
```

## Safety
- Always use fuse on solar input
- Common ground between all modules
- Power ESP32 via USB during testing
- Verify with multimeter
- Start with short outdoor tests

## Repo
This is designed to be plug-and-play - clone, follow README, flash and go.
