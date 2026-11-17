"""One-shot HTTP server for the SolarLab Mini JSON API."""

import socket  # TCP sockets for the HTTP listener
import json  # Encode the latest reading as a JSON string


class WebServer:
    """Serve the latest sensor reading to at most one client per call."""

    def __init__(self, get_data_callback, port=80):
        """Create a non-blocking listener that asks get_data_callback for replies."""
        self.get_data = get_data_callback  # Function returning the latest reading dict
        self.port = port  # TCP port to listen on (80 is the default HTTP port)
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # Listening TCP socket
        self.s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # Allow fast restarts
        self.s.bind(('0.0.0.0', port))  # Accept clients on every interface
        self.s.listen(5)  # Allow up to five queued connections
        self.s.settimeout(1)  # Never wait longer than one second for a client

    def handle_once(self):
        """Accept one client, reply with JSON, and never block the sensor loop."""
        try:
            conn, addr = self.s.accept()  # conn: client socket, addr: (ip, port) tuple
        except OSError:
            return  # No client arrived: normal timeout, nothing to do
        try:
            conn.settimeout(2)  # Bound how long a slow client can stall us
            conn.recv(1024)  # Read the HTTP request; any request gets the same reply
            data = self.get_data()  # Fetch the freshest voltage/current/power snapshot
            body = json.dumps(data)  # Serialize the snapshot into JSON text
            response = (  # Full HTTP response with CORS for browser/dashboard clients
                'HTTP/1.1 200 OK\r\n'
                'Content-Type: application/json\r\n'
                'Access-Control-Allow-Origin: *\r\n'
                'Content-Length: ' + str(len(body)) + '\r\n'
                'Connection: close\r\n'
                '\r\n' + body
            )
            conn.sendall(response.encode())  # Send every byte before closing
        except OSError as e:  # e is a socket send/receive error
            print('server error', e)  # Log the failure and keep the main loop alive
        finally:
            conn.close()  # Always release the client socket
