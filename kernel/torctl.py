"""torctl.py -- Tor control interface for Tether OS
Signals Tor to create a new circuit (SIGNAL NEWNYM).
Communicates via Tor's control port (default 9051).
"""

import socket
import time
import re


class TorCtl:
    def __init__(self, host="127.0.0.1", port=9051, password=None):
        self.host = host
        self.port = port
        self.password = password

    def _connect(self):
        sock = socket.create_connection((self.host, self.port), timeout=5)
        self._authenticate(sock)
        return sock

    def _authenticate(self, sock):
        if self.password:
            self._send(sock, f'AUTHENTICATE "{self.password}"')
        else:
            self._send(sock, "AUTHENTICATE")
        resp = self._recv(sock)
        if not resp.startswith("250"):
            raise RuntimeError(f"Tor auth failed: {resp}")

    def _send(self, sock, cmd):
        sock.sendall(f"{cmd}\r\n".encode())

    def _recv(self, sock):
        data = b""
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            data += chunk
            if b"\r\n" in data:
                break
        return data.decode().strip()

    def newnym(self):
        sock = self._connect()
        try:
            self._send(sock, "SIGNAL NEWNYM")
            resp = self._recv(sock)
            if not resp.startswith("250"):
                raise RuntimeError(f"NEWNYM failed: {resp}")
            # Tor needs a brief moment to build the new circuit
            time.sleep(0.5)
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
