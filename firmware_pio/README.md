# SolarLab Mini - PlatformIO Version

This is the Arduino C++ version for ESP32-WROOM using PlatformIO.

## Quick Start
1. Open this folder in VS Code with PlatformIO extension
2. PlatformIO will auto-install dependencies
3. Connect ESP32 via USB
4. Click Upload (or `pio run --target upload`)
5. Monitor with `pio device monitor`

## Features
- WiFi AP: SolarLab-Mini / solarlab123
- INA219 voltage/current/power reading
- SSD1306 OLED display
- HTTP JSON endpoint at http://192.168.4.1/data
- CORS enabled for laptop dashboard

## Wiring
Same as before - see ../docs/wiring.md

## Libraries (auto-installed)
- Adafruit INA219
- Adafruit SSD1306
- Adafruit GFX
- ArduinoJson
