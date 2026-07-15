"""probe.py -- IP detection and verification for Tether OS
Queries external services to confirm public IP address.
"""

import socket
import urllib.request


_SERVICES = [
    "https://api.ipify.org",
    "https://icanhazip.com",
    "https://ifconfig.me/ip",
]


class Probe:
    def __init__(self, proxy_host="127.0.0.1", proxy_port=9050):
        self.proxy_host = proxy_host
        self.proxy_port = proxy_port

    def _proxy_support(self):
        return urllib.request.ProxyHandler({
            "http": f"socks5://{self.proxy_host}:{self.proxy_port}",
            "https": f"socks5h://{self.proxy_host}:{self.proxy_port}",
        })

    def get_ip(self, use_tor=True):
        for url in _SERVICES:
            try:
                if use_tor:
                    opener = urllib.request.build_opener(self._proxy_support())
                    resp = opener.open(url, timeout=10)
                else:
                    resp = urllib.request.urlopen(url, timeout=10)
                ip = resp.read().decode().strip()
                if self._valid_ip(ip):
                    return ip
            except Exception:
                continue
        return None

    def get_current_ip(self):
        return self.get_ip(use_tor=True)

    @staticmethod
    def _valid_ip(addr):
        try:
            socket.inet_aton(addr)
            return True
        except OSError:
            return False
