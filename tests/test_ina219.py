import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "firmware"))

from drivers.ina219 import INA219  # noqa: E402


class FakeI2C:
    def __init__(self, regs):
        self.regs = regs

    def readfrom_mem(self, addr, reg, n):
        value = self.regs.get(reg, 0) & 0xFFFF
        return bytes([(value >> 8) & 0xFF, value & 0xFF])

    def writeto_mem(self, addr, reg, data):
        self.regs[reg] = (data[0] << 8) | data[1]


def make_ina(shunt_raw=0, bus_raw=0):
    return INA219(FakeI2C({0x01: shunt_raw, 0x02: bus_raw}))


def test_bus_voltage_scaling():
    bus_raw = int(5.0 / 0.004) << 3
    assert make_ina(bus_raw=bus_raw).get_bus_voltage() == pytest.approx(5.0, abs=0.005)


def test_bus_voltage_zero():
    assert make_ina(bus_raw=0).get_bus_voltage() == pytest.approx(0.0, abs=0.001)


def test_shunt_voltage_positive():
    assert make_ina(shunt_raw=10000).get_shunt_voltage() == pytest.approx(100.0, abs=0.01)


def test_shunt_voltage_negative():
    assert make_ina(shunt_raw=-10000).get_shunt_voltage() == pytest.approx(-100.0, abs=0.01)


def test_current_with_01_ohm_shunt():
    assert make_ina(shunt_raw=10000).get_current() == pytest.approx(1.0, rel=1e-3)


def test_current_negative():
    assert make_ina(shunt_raw=-10000).get_current() == pytest.approx(-1.0, rel=1e-3)


def test_current_zero():
    assert make_ina(shunt_raw=0).get_current() == pytest.approx(0.0, abs=1e-6)


def test_power_matches_v_times_i():
    bus_raw = int(5.0 / 0.004) << 3
    assert make_ina(shunt_raw=10000, bus_raw=bus_raw).get_power() == pytest.approx(5.0, rel=1e-3)
