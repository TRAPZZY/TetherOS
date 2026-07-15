"""rotator.py -- Core IP rotation engine for Tether OS
Orchestrates Tor circuit renewal and IP verification.
"""

from kernel.torctl import TorCtl
from kernel.probe import Probe


class Rotator:
    def __init__(self, config=None):
        self.config = config or {}
        self.tor = TorCtl(
            host=self.config.get("tor_host", "127.0.0.1"),
            port=self.config.get("tor_control_port", 9051),
            password=self.config.get("tor_password"),
        )
        self.probe = Probe(
            proxy_host=self.config.get("tor_host", "127.0.0.1"),
            proxy_port=self.config.get("tor_socks_port", 9050),
        )
        self._last_ip = None
        self._rotations = 0

    def rotate(self):
        old_ip = self.probe.get_current_ip()
        self.tor.newnym()
        new_ip = self.probe.get_current_ip()
        self._rotations += 1
        self._last_ip = new_ip
        return {
            "success": new_ip is not None and new_ip != old_ip,
            "old_ip": old_ip,
            "new_ip": new_ip,
            "rotations": self._rotations,
        }

    def status(self):
        return {
            "current_ip": self._last_ip or self.probe.get_current_ip(),
            "total_rotations": self._rotations,
        }
