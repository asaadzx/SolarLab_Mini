"""Hardware and network configuration for the SolarLab Mini ESP32 firmware.

The OLED display and the INA219 sensor deliberately use two separate I2C buses:
the OLED is on I2C(0), while the INA219 is on I2C(1).
"""

AP_SSID = "SolarLab-Mini"       # Wi-Fi network name broadcast by the ESP32
AP_PASSWORD = "solarlab123"     # WPA password for that access point

# --- OLED display on I2C bus 0 (verified wiring) ---
OLED_SDA = 23                   # GPIO connected to the OLED SDA pin
OLED_SCL = 21                   # GPIO connected to the OLED SCL pin
OLED_ADDR = 0x3C                # I2C address reported by the SSD1306 module

# --- INA219 sensor on I2C bus 1 (verified wiring) ---
INA_SDA = 19                    # GPIO connected to the INA219 SDA pin
INA_SCL = 18                    # GPIO connected to the INA219 SCL pin
INA219_ADDR = 0x40              # I2C address reported by the INA219 module

POLLS = 1                       # Seconds between sensor reads and display updates
