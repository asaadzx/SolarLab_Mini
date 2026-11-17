import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "firmware"))

import webserver  # noqa: E402


class FakeConn:
    def __init__(self):
        self.timeouts = []
        self.sent = []
        self.closed = False

    def settimeout(self, value):
        self.timeouts.append(value)

    def recv(self, size):
        return b"GET /data HTTP/1.1\r\nHost: esp\r\n\r\n"

    def sendall(self, data):
        self.sent.append(data)

    def close(self):
        self.closed = True


class FakeServerSocket:
    def __init__(self, conn=None, accept_error=None):
        self.conn = conn
        self.accept_error = accept_error
        self.calls = []

    def setsockopt(self, *args):
        self.calls.append(("setsockopt", args))

    def bind(self, *args):
        self.calls.append(("bind", args))

    def listen(self, *args):
        self.calls.append(("listen", args))

    def settimeout(self, *args):
        self.calls.append(("settimeout", args))

    def accept(self):
        if self.accept_error:
            raise self.accept_error
        return self.conn, ("127.0.0.1", 4321)


def make_server(monkeypatch, fake_socket):
    monkeypatch.setattr(webserver.socket, "socket", lambda *args: fake_socket)
    return webserver.WebServer(lambda: {"voltage": 4.5})


def test_handle_once_sends_json_with_timeouts(monkeypatch):
    conn = FakeConn()
    server = make_server(monkeypatch, FakeServerSocket(conn))
    server.handle_once()
    assert conn.timeouts == [2]
    assert conn.closed is True
    text = b"".join(conn.sent).decode()
    assert "HTTP/1.1 200 OK" in text
    assert "Access-Control-Allow-Origin: *" in text
    assert '"voltage": 4.5' in text
    assert ("settimeout", (1,)) in server.s.calls


def test_handle_once_ignores_accept_timeout(monkeypatch):
    server = make_server(monkeypatch, FakeServerSocket(accept_error=OSError("timeout")))
    server.handle_once()
