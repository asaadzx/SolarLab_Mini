import network
from config import AP_SSID, AP_PASSWORD

def start_ap():
    ap = network.WLAN(network.AP_IF)
    ap.active(True)
    try:
        ap.config(essid=AP_SSID, password=AP_PASSWORD)
    except Exception as e:
        print('AP config error:', e)
        ap.config(essid=AP_SSID)
    print('AP started:', ap.ifconfig())
    return ap
