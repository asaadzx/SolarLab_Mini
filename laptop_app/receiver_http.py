"""Poll the ESP32 JSON endpoint and append each reading to a CSV file."""

import requests  # HTTP client used to fetch /data
import csv  # Write the readings as comma-separated values
import time  # Sleep between polls and produce epoch timestamps
from datetime import datetime  # Human-readable timestamps
import os  # Create the output directory

ESP_URL = "http://192.168.4.1/data"  # Endpoint on the ESP32 access point
OUT_DIR = "data/exports"  # Folder where CSV files are written
os.makedirs(OUT_DIR, exist_ok=True)  # Create the folder if it does not exist


def main():
    """Log sensor readings until the user presses Ctrl+C."""
    fname = os.path.join(  # fname is this run's output file path
        OUT_DIR, f"solarlab_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"  # Timestamped name
    )
    with open(fname, 'w', newline='') as f:  # f is the open CSV file
        writer = csv.writer(f)  # writer serializes rows into CSV
        writer.writerow(['timestamp', 'datetime', 'voltage_v', 'current_a', 'power_w'])  # Header row
        print(f'Logging to {fname}. Press Ctrl+C to stop.')  # Instructions
        try:
            while True:  # Poll forever until interrupted
                try:
                    r = requests.get(ESP_URL, timeout=3)  # r is the HTTP response
                    j = r.json()  # j is the parsed JSON dict from the ESP32
                    ts = datetime.now().isoformat()  # Human-readable local time
                    writer.writerow([time.time(), ts, j.get('voltage'), j.get('current'), j.get('power')])
                    f.flush()  # Make each row visible immediately
                    print(ts, j)  # Echo the reading to the terminal
                except Exception as e:  # e is a network or JSON error
                    print('err:', e)  # Report it and keep logging
                time.sleep(1)  # One reading per second
        except KeyboardInterrupt:  # User pressed Ctrl+C
            print('Stopped.')  # Farewell message


if __name__ == '__main__':  # Only run when invoked as a script
    main()  # Start the logging loop
