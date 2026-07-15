"""scheduler.py -- Timer daemon for Tether OS
Triggers IP rotation at configurable intervals (default: 60s).
"""

import time
import threading
import logging

from kernel.rotator import Rotator

logging.basicConfig(level=logging.INFO, format="[TETHER] %(asctime)s %(message)s")
log = logging.getLogger("tether.scheduler")


class Scheduler:
    def __init__(self, interval=60, config=None):
        self.interval = interval
        self.rotator = Rotator(config)
        self._running = False
        self._thread = None
        self._log = []

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        log.info(f"Scheduler started -- rotating IP every {self.interval}s")
        return {"status": "started", "interval": self.interval}

    def stop(self):
        self._running = False
        log.info("Scheduler stopped")
        return {"status": "stopped"}

    def _loop(self):
        while self._running:
            try:
                result = self.rotator.rotate()
                ip = result.get("new_ip", "unknown")
                status = "OK" if result["success"] else "FAIL"
                log.info(f"Rotation #{result['rotations']}: {result['old_ip']} -> {ip} [{status}]")
                self._log.append(result)
            except Exception as e:
                log.error(f"Rotation failed: {e}")
            time.sleep(self.interval)

    def summary(self):
        return {
            "running": self._running,
            "interval": self.interval,
            "total_rotations": self.rotator.status()["total_rotations"],
            "current_ip": self.rotator.status()["current_ip"],
            "log": self._log[-10:] if self._log else [],
        }
