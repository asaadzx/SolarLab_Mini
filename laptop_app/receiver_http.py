import requests
import csv
import time
from datetime import datetime
import os

ESP_URL = "http://192.168.4.1/data"
OUT_DIR = "data/exports"
os.makedirs(OUT_DIR, exist_ok=True)

def main():
    fname = os.path.join(OUT_DIR, f"solarlab_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
    with open(fname, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['timestamp', 'datetime', 'voltage_v', 'current_a', 'power_w'])
        print(f'Logging to {fname}. Press Ctrl+C to stop.')
        try:
            while True:
                try:
                    r = requests.get(ESP_URL, timeout=3)
                    j = r.json()
                    ts = datetime.now().isoformat()
                    writer.writerow([time.time(), ts, j.get('voltage'), j.get('current'), j.get('power')])
                    f.flush()
                    print(ts, j)
                except Exception as e:
                    print('err:', e)
                time.sleep(1)
        except KeyboardInterrupt:
            print('Stopped.')

if __name__ == '__main__':
    main()
