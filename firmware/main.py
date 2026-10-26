import machine
import time
from machine import I2C, Pin
from drivers.ssd1306 import SSD1306
from drivers.ina219 import INA219
from wifi_ap import start_ap
from webserver import WebServer
import config

# I2C
i2c = I2C(0, scl=Pin(config.I2C_SCL), sda=Pin(config.I2C_SDA))
print('I2C scan:', [hex(x) for x in i2c.scan()])

# Sensors
oled = SSD1306(128, 64, i2c, addr=config.OLED_ADDR)
try:
    ina = INA219(i2c, addr=config.INA219_ADDR)
    sensor_ok = True
except Exception as e:
    print('INA219 init error:', e)
    sensor_ok = False

# WiFi AP
ap = start_ap()

data = {'voltage': 0, 'current': 0, 'power': 0, 'timestamp': 0}

def get_data():
    return data

server = WebServer(get_data)

def update():
    global data
    try:
        if sensor_ok:
            v = ina.get_bus_voltage()
            i = ina.get_current()
            p = v * i if v and i else 0
        else:
            v, i, p = 0, 0, 0
        data = {'voltage': round(v, 3), 'current': round(i, 3), 'power': round(p, 3), 'timestamp': time.time()}
        # Update OLED
        oled.fill(0)
        oled.text('SolarLab Mini', 0, 0)
        oled.text('V:{:.2f}V'.format(v), 0, 16)
        oled.text('I:{:.3f}A'.format(i), 0, 28)
        oled.text('P:{:.2f}W'.format(p), 0, 40)
        oled.show()
    except Exception as e:
        print('update error:', e)

# Main loop
while True:
    update()
    server.handle_once()
    time.sleep(1)
