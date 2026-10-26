import socket
import json
import time

class WebServer:
    def __init__(self, get_data_callback):
        self.get_data = get_data_callback
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.s.bind(('0.0.0.0', 80))
        self.s.listen(5)
        self.s.settimeout(1)
        
    def handle_once(self):
        try:
            conn, addr = self.s.accept()
            req = conn.recv(1024)
            # Simple response
            data = self.get_data()
            response = json.dumps(data)
            html = 'HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nAccess-Control-Allow-Origin: *\r\n\r\n' + response
            conn.send(html.encode())
            conn.close()
        except OSError:
            pass
        except Exception as e:
            print('server error', e)
