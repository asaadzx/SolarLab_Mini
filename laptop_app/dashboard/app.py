"""Flask dashboard that proxies the ESP32 sensor reading for the browser."""

from flask import Flask, render_template, jsonify  # Web framework and JSON helpers
import requests  # HTTP client used to fetch /data from the ESP32

app = Flask(__name__)  # app is the Flask web application
ESP_URL = "http://192.168.4.1/data"  # Sensor endpoint on the ESP32 access point


@app.route('/')  # Serve the dashboard page at the root URL
def index():
    """Render the dashboard HTML template."""
    return render_template('index.html')  # HTML lives in templates/index.html


@app.route('/api/latest')  # Serve the newest reading as JSON
def latest():
    """Fetch /data from the ESP32 and return it; report errors as JSON."""
    try:
        r = requests.get(ESP_URL, timeout=2)  # r is the HTTP response from the board
        return jsonify(r.json())  # Forward the parsed JSON to the browser
    except Exception as e:  # e is a network or JSON error
        return jsonify({'error': str(e)})  # Always return valid JSON


if __name__ == '__main__':  # Only run when invoked as a script
    app.run(host='127.0.0.1', port=5000, debug=True)  # Local development server
