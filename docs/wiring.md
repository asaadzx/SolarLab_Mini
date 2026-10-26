# Wiring Guide

## I2C Connections
| ESP32-WROOM | INA219 | OLED SSD1306 |
|-------------|--------|--------------|
| 3.3V | VCC | VCC |
| GND | GND | GND |
| GPIO21 (SDA) | SDA | SDA |
| GPIO22 (SCL) | SCL | SCL |

## Solar Input (with fuse)
1. Panel (+) -> Inline Fuse -> INA219 VIN+
2. Panel (-) -> Common GND
3. INA219 VIN- -> (measure across load/terminals as appropriate)
4. Ensure all GND connected together

## Safety Notes
- Use 1A or 2A fast-blow fuse
- Don't power ESP32 from 18V panel
- Power ESP32 via USB during breadboard tests
- Use multimeter to verify voltages
- Keep wires insulated
