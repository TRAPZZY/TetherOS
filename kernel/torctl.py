"""torctl.py -- Tor control interface for Tether OS
Signals Tor to create a new circuit (SIGNAL NEWNYM).
Communicates via Tor's control port (default 9051).
"""

import socket
import time
import os


class TorCtl:
    def __init__(self, host="127.0.0.1", port=9051, password=None, cookie_path=None):
        self.host = host
        self.port = port
        self.password = password
        self.cookie_path = cookie_path

    def _connect(self):
        sock = socket.create_connection((self.host, self.port), timeout=5)
        self._authenticate(sock)
        return sock

    def _authenticate(self, sock):
        if self.password:
            escaped = str(self.password).replace("\\", "\\\\").replace('"', '\\"')
            self._send(sock, f'AUTHENTICATE "{escaped}"')
        else:
            cookie = self._read_cookie()
            self._send(sock, f"AUTHENTICATE {cookie.hex()}" if cookie else "AUTHENTICATE")
        resp = self._recv(sock)
        if not resp.startswith("250"):
            raise RuntimeError(f"Tor auth failed: {resp}")

    def _read_cookie(self):
        candidates = [
            self.cookie_path,
            "/run/tor/control.authcookie",
            "/var/lib/tor/control_auth_cookie",
            os.path.expanduser("~/.tor/control_auth_cookie"),
        ]
        for path in candidates:
            if not path:
                continue
            try:
                with open(path, "rb") as handle:
                    cookie = handle.read(32)
                if len(cookie) == 32:
                    return cookie
            except OSError:
                continue
        return None

    def _send(self, sock, cmd):
        sock.sendall(f"{cmd}\r\n".encode())

    def _recv(self, sock):
        data = b""
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            data += chunk
            lines = data.split(b"\r\n")
            for line in lines[:-1]:
                if len(line) >= 4 and line[:3].isdigit() and line[3:4] == b" ":
                    return data.decode("utf-8", errors="replace").strip()
        return data.decode().strip()

    def newnym(self):
        sock = self._connect()
        try:
            self._send(sock, "SIGNAL NEWNYM")
            resp = self._recv(sock)
            if not resp.startswith("250"):
                raise RuntimeError(f"NEWNYM failed: {resp}")
            return True
        finally:
            sock.close()

    def get_circuit_count(self):
        sock = self._connect()
        try:
            self._send(sock, "GETINFO circuit-status")
            resp = self._recv(sock)
            return resp.count("BUILT")
        finally:
            sock.close()

    def is_available(self):
        try:
            sock = self._connect()
            sock.close()
            return True
        except (OSError, RuntimeError):
            return False
