"""One-shot HTTP server for the SolarLab Mini JSON API."""

import socket
import json


class WebServer:
    """Serve the latest sensor reading to at most one client per call."""

    def __init__(self, get_data_callback, port=80):
        self.get_data = get_data_callback
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.s.bind(('0.0.0.0', port))
        self.s.listen(5)
        self.s.settimeout(1)

    def handle_once(self):
        """Accept one client, reply with JSON, and never block the sensor loop."""
        try:
            conn, addr = self.s.accept()
        except OSError:
            return
        try:
            conn.settimeout(2)
            conn.recv(1024)
            data = self.get_data()
            body = json.dumps(data)
            response = (
                'HTTP/1.1 200 OK\r\n'
                'Content-Type: application/json\r\n'
                'Access-Control-Allow-Origin: *\r\n'
                'Content-Length: ' + str(len(body)) + '\r\n'
                'Connection: close\r\n'
                '\r\n' + body
            )
            conn.sendall(response.encode())
        except OSError as e:
            print('server error', e)
        finally:
            conn.close()
