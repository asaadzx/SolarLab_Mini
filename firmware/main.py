"""Main application: read the INA219, update the OLED, and serve JSON over Wi-Fi.

Both peripherals are optional at startup so a missing or broken display/sensor
cannot stop the access point from coming online.
"""

import machine  # ESP32 hardware module (kept available for board-level access)
import time  # Provides sleep() and the timestamp used in the JSON payload
from machine import I2C, Pin  # I2C bus and GPIO pin classes
from drivers.ssd1306 import SSD1306  # Minimal OLED display driver
from drivers.ina219 import INA219  # Current, bus voltage, and power sensor driver
from wifi_ap import start_ap  # Starts the SolarLab-Mini access point
from webserver import WebServer  # Serves the /data JSON response
import config  # Pin map, I2C addresses, and AP credentials

# Two independent I2C buses avoid address/pin conflicts between the two devices.
i2c_oled = I2C(0, scl=Pin(config.OLED_SCL), sda=Pin(config.OLED_SDA))  # Bus 0: display
i2c_ina = I2C(1, scl=Pin(config.INA_SCL), sda=Pin(config.INA_SDA))     # Bus 1: sensor
print('OLED bus scan:', [hex(x) for x in i2c_oled.scan()])  # List display I2C addresses
print('INA219 bus scan:', [hex(x) for x in i2c_ina.scan()])  # List sensor I2C addresses

# Display initialization is non-fatal: the AP and sensor can still work without it.
try:
    oled = SSD1306(128, 64, i2c_oled, addr=config.OLED_ADDR)  # 128x64 pixel display
    display_ok = True  # True means the display is safe to use in update()
except Exception as e:  # e is the OLED init error (for example ENODEV)
    print('OLED init error:', e)  # Report the problem on the serial console
    oled = None  # No display object available
    display_ok = False  # Skip display updates from now on

# Sensor initialization is non-fatal too, and the probe proves the chip answers.
try:
    ina = INA219(i2c_ina, addr=config.INA219_ADDR)  # Sensor object on I2C bus 1
    ina.get_bus_voltage()  # Probe: a dead/absent chip raises here
    sensor_ok = True  # True means sensor readings are trustworthy
except Exception as e:  # e is the INA219 init or probe error
    print('INA219 init error:', e)  # Report the problem on the serial console
    ina = None  # No sensor object available
    sensor_ok = False  # Served readings will stay at zero

# Wi-Fi AP is started even if a peripheral failed, so /data remains reachable.
ap = start_ap()  # ap is the active network.WLAN access-point object

# Latest readings shared with the webserver. Replacing the whole dict at once
# avoids the server ever seeing a half-updated voltage/current/power set.
data = {'voltage': 0, 'current': 0, 'power': 0, 'timestamp': 0}


def get_data():
    """Return the latest reading dict to the webserver callback."""
    return data  # The current snapshot of voltage, current, power, timestamp


server = WebServer(get_data)  # HTTP server that asks get_data() for each reply


def update():
    """Sample the sensor once, store the snapshot, and redraw the OLED."""
    global data  # We replace the module-level snapshot dict here
    v, i, p = 0, 0, 0  # v: bus volts, i: amps, p: watts; zero if unavailable
    try:
        if sensor_ok:  # Only touch the sensor object if init succeeded
            v = ina.get_bus_voltage()  # Bus voltage in volts
            i = ina.get_current()      # Shunt-derived current in amps
            p = v * i if v and i else 0  # Power in watts, or 0 if either is zero
    except Exception as e:  # e is a runtime I2C/read error
        print('sensor read error:', e)  # Keep serving the last valid values
    data = {'voltage': round(v, 3), 'current': round(i, 3),
            'power': round(p, 3), 'timestamp': time.time()}  # Atomic snapshot
    try:
        if display_ok:  # Only touch the display object if init succeeded
            oled.fill(0)  # Clear the frame buffer to black
            oled.text('SolarLab Mini', 0, 0)  # Title on the first text row
            oled.text('V:{:.2f}V'.format(v), 0, 16)  # Voltage on row two
            oled.text('I:{:.3f}A'.format(i), 0, 28)  # Current on row three
            oled.text('P:{:.2f}W'.format(p), 0, 40)  # Power on row four
            oled.show()  # Push the frame buffer to the physical display
    except Exception as e:  # e is a runtime display/I2C error
        print('display error:', e)  # A bad display must not stop the server


# Main loop: sample, serve at most one client, then sleep before the next sample.
while True:
    update()  # Refresh data and OLED
    server.handle_once()  # Answer one HTTP request if one is waiting
    time.sleep(1)  # One-second polling interval
