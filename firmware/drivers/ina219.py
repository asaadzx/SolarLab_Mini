"""Simple INA219 driver for MicroPython.

Register facts used below: 0x01 is a signed 16-bit shunt register with 10 uV
per LSB, 0x02 holds bus voltage in bits 15:3 at 4 mV per LSB, and the current
calculation assumes the module's 0.1 ohm shunt resistor.
"""

import time  # Kept for compatibility with code that may time conversions


class INA219:
    """Read bus voltage, shunt voltage, current, and power from an INA219."""

    def __init__(self, i2c, addr=0x40):
        """Attach the sensor to an I2C bus at the given 7-bit address."""
        self.i2c = i2c  # I2C bus object used for all register reads/writes
        self.addr = addr  # I2C address of the INA219 (0x40 by default)
        # Calibration fields are kept for compatibility; this driver derives
        # current from the shunt register instead of the calibration register.
        self._cal_value = 4096  # Legacy calibration value (not written to the chip)
        self._current_lsb = 0.001  # Legacy 1 mA approximation (not used here)
        self._power_lsb = 0.02  # Legacy power LSB (not used here)

    def _read_register(self, reg):
        """Read one 16-bit big-endian register from the sensor."""
        data = self.i2c.readfrom_mem(self.addr, reg, 2)  # Two raw bytes from reg
        return (data[0] << 8) | data[1]  # Combine them into an unsigned integer

    def _write_register(self, reg, value):
        """Write one 16-bit big-endian register to the sensor."""
        data = bytearray([(value >> 8) & 0xFF, value & 0xFF])  # High byte, low byte
        self.i2c.writeto_mem(self.addr, reg, data)  # Send both bytes to reg

    def get_bus_voltage(self):
        """Return the bus voltage at VIN- in volts (4 mV per LSB)."""
        val = self._read_register(0x02)  # Raw bus-voltage register (also status bits)
        # Check if conversion ready
        if val & 0x0001:  # Bit 0 signals a math overflow; no action needed here
            pass  # Overflow would require a different shunt/PGA setting
        voltage = ((val >> 3) * 0.004)  # Bits 15:3 carry volts in 4 mV steps
        return voltage  # Bus voltage in volts

    def get_shunt_voltage(self):
        """Return the signed voltage across the 0.1 ohm shunt in millivolts."""
        val = self._read_register(0x01)  # Raw shunt-voltage register (10 uV per LSB)
        # Signed 16-bit
        if val > 0x7FFF:  # Values above 0x7FFF are negative in two's complement
            val -= 0x10000  # Convert to a signed Python integer
        return val * 0.01  # 10 uV per bit equals 0.01 mV per bit

    def get_current(self):
        """Return current in amps, derived from shunt voltage / 0.1 ohm."""
        # Shunt voltage is returned in mV; convert to V then apply Ohm's law
        shunt_v = self.get_shunt_voltage() / 1000.0  # mV -> V
        shunt_ohm = 0.1  # Resistance of the shunt built into the module
        return shunt_v / shunt_ohm  # A (volts divided by ohms)

    def get_power(self):
        """Return apparent power in watts (bus volts times shunt-derived amps)."""
        v = self.get_bus_voltage()  # Bus voltage in volts
        i = self.get_current()  # Current in amps
        return v * i  # Power in watts
