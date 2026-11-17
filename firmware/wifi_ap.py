"""Access-point setup for the SolarLab Mini ESP32 firmware."""

import network  # ESP32 Wi-Fi interface driver
from config import AP_SSID, AP_PASSWORD  # Network name and password from config.py


def start_ap():
    """Start the Wi-Fi access point and return its active WLAN object."""
    ap = network.WLAN(network.AP_IF)  # ap is the ESP32's soft access-point interface
    ap.active(True)  # Power on the access-point radio
    try:
        ap.config(essid=AP_SSID, password=AP_PASSWORD)  # Configure the protected network
    except Exception as e:  # e is a WPA configuration rejection from the radio
        print('AP config error:', e)  # Report the rejected configuration
        ap.config(essid=AP_SSID)  # Fallback: open network with the same name
    print('AP started:', ap.ifconfig())  # Show the assigned IP, mask, and gateway
    return ap  # Caller keeps the object so the AP stays active
