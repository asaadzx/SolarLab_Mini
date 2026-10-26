from flask import Flask, render_template, jsonify
import requests

app = Flask(__name__)
ESP_URL = "http://192.168.4.1/data"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/latest')
def latest():
    try:
        r = requests.get(ESP_URL, timeout=2)
        return jsonify(r.json())
    except Exception as e:
        return jsonify({'error': str(e)})

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=True)
