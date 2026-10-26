# Simple INA219 driver for MicroPython
# Minimal implementation for voltage/current/power

import time

class INA219:
    def __init__(self, i2c, addr=0x40):
        self.i2c = i2c
        self.addr = addr
        # Configure with default settings
        # For basic reading, some modules work with defaults
        self._cal_value = 4096
        self._current_lsb = 0.001  # 1mA default approximation
        self._power_lsb = 0.02

    def _read_register(self, reg):
        data = self.i2c.readfrom_mem(self.addr, reg, 2)
        return (data[0] << 8) | data[1]

    def _write_register(self, reg, value):
        data = bytearray([(value >> 8) & 0xFF, value & 0xFF])
        self.i2c.writeto_mem(self.addr, reg, data)

    def get_bus_voltage(self):
        # Bus voltage register 0x02, shifted
        val = self._read_register(0x02)
        # Check if conversion ready
        if val & 0x0001:
            pass
        voltage = ((val >> 3) * 0.004)  # 4mV per bit
        return voltage

    def get_shunt_voltage(self):
        val = self._read_register(0x01)
        # Signed 16-bit
        if val > 0x7FFF:
            val -= 0x10000
        return val * 0.01  # 10uV per bit

    def get_current(self):
        # Simplified - use shunt voltage / shunt resistance if known
        # Default shunt often 0.1 ohm
        shunt_mv = self.get_shunt_voltage() / 1000.0  # convert uV to mV
        shunt_ohm = 0.1
        current = shunt_mv / shunt_ohm  # mA if mV/ohm
        return current / 1000.0  # A

    def get_power(self):
        v = self.get_bus_voltage()
        i = self.get_current()
        return v * i
