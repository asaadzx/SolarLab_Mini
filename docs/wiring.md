# Wiring Guide

The circuit has three separate groups of connections. Build them in this order.

## 1. Power loop (series circuit)

```
Panel (+) ── Fuse ── INA219 VIN+ ──[0.1 Ω shunt inside INA219]── VIN− ── Load (+) ── Load (−) ── Panel (−)
```

| From | To |
|---|---|
| Panel **+** | Fuse input |
| Fuse output | INA219 **VIN+** |
| INA219 **VIN−** | Load **+** |
| Load **−** | Panel **−** |

The 0.1 Ω shunt is already inside the INA219 module. Never bridge VIN+ to VIN−
with a wire: that bypasses the shunt and current will always read zero.

With no load attached, VIN− still sees the panel voltage through the shunt, so
`bus_v` should read roughly the panel's open-circuit voltage. That is a useful
sanity check before connecting a load.

## 2. Common ground node

All four of these must be the **same electrical point**:

```
Panel (−) ── Load (−) ── INA219 GND ── ESP32 GND
```

Without this shared reference, `bus_v` floats near 0 V even when the panel is lit.

## 3. I2C signal wiring

| ESP32 pin | INA219 | OLED SSD1306 |
|---|---|---|
| 3V3 | VCC | VCC |
| GND | GND (same node as above) | GND (same node as above) |
| GPIO19 SDA (I2C1) | SDA | — |
| GPIO18 SCL (I2C1) | SCL | — |
| GPIO23 SDA (I2C0) | — | SDA |
| GPIO21 SCL (I2C0) | — | SCL |

The devices use **different I2C buses**, so the similar wiring must not be mixed up.

## Safety notes

- Use a DC fuse rated above the panel's open-circuit voltage and about 1.5× its
  short-circuit current.
- Keep panel voltage below 26 V and load current below 3.2 A (INA219 shunt limit).
- Power the ESP32 from USB while testing; never connect an 18 V panel to 3V3 or GPIO.
- Verify voltages with a multimeter before closing the circuit.
- Batteries require a chemistry-matched charge controller (for example TP4056 for
  a single Li-ion cell); connect the battery to the charger's BAT terminals, never
  directly to VIN+/VIN− or the ESP32.
- A small DC motor is a near short when stalled: it will collapse the panel voltage.
  Use a resistive load (bulb, or LED plus a series resistor) for first tests.
- Keep all connections insulated and make changes with USB and panel disconnected.
