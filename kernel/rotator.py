"""rotator.py -- Core IP rotation engine for Tether OS
Orchestrates Tor circuit renewal and IP verification.
"""

from kernel.torctl import TorCtl
from kernel.probe import Probe
import time


class Rotator:
    def __init__(self, config=None):
        self.config = config or {}
        self.tor = TorCtl(
            host=self.config.get("tor_host", "127.0.0.1"),
            port=self.config.get("tor_control_port", 9051),
            password=self.config.get("tor_password"),
            cookie_path=self.config.get("tor_cookie_path"),
        )
        self.probe = Probe(
            proxy_host=self.config.get("tor_host", "127.0.0.1"),
            proxy_port=self.config.get("tor_socks_port", 9050),
        )
        self._last_ip = None
        self._rotations = 0
        self._attempts = 0
        self.settle_timeout = float(self.config.get("rotation_settle_timeout", 15))
        self.poll_interval = float(self.config.get("rotation_poll_interval", 2))

    def rotate(self):
        self._attempts += 1
        old_ip = self.probe.get_current_ip()
        try:
            self.tor.newnym()
        except (OSError, RuntimeError) as exc:
            return {
                "success": False,
                "old_ip": old_ip,
                "new_ip": None,
                "rotations": self._rotations,
                "attempts": self._attempts,
                "error": str(exc),
            }

        deadline = time.monotonic() + self.settle_timeout
        new_ip = None
        while True:
            new_ip = self.probe.get_current_ip()
            if new_ip is not None and (old_ip is None or new_ip != old_ip):
                self._rotations += 1
                self._last_ip = new_ip
                break
            if time.monotonic() >= deadline:
                break
            time.sleep(self.poll_interval)
        return {
            "success": new_ip is not None and (old_ip is None or new_ip != old_ip),
            "old_ip": old_ip,
            "new_ip": new_ip,
            "rotations": self._rotations,
            "attempts": self._attempts,
            **({"error": "Tor did not produce a different exit IP before timeout"}
               if new_ip is None or new_ip == old_ip else {}),
        }

    def status(self):
        return {
            "current_ip": self._last_ip,
            "total_rotations": self._rotations,
            "total_attempts": self._attempts,
        }
