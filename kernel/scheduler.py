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
    def __init__(self, interval=60, config=None, on_rotation=None,
                 rotate_immediately=False, rotator=None):
        if int(interval) < 1:
            raise ValueError("rotation interval must be at least one second")
        self.interval = interval
        self.rotator = rotator or Rotator(config)
        self.on_rotation = on_rotation
        self.rotate_immediately = rotate_immediately
        self._running = False
        self._thread = None
        self._log = []
        self._stop_event = threading.Event()

    def start(self):
        if self._running:
            return {"status": "already-running", "interval": self.interval}
        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        log.info(f"Scheduler started -- rotating IP every {self.interval}s")
        return {"status": "started", "interval": self.interval}

    def stop(self):
        self._running = False
        self._stop_event.set()
        if self._thread and self._thread is not threading.current_thread():
            self._thread.join(timeout=2)
        log.info("Scheduler stopped")
        return {"status": "stopped"}

    def _loop(self):
        if not self.rotate_immediately and self._stop_event.wait(self.interval):
            return
        while self._running:
            try:
                result = self.rotator.rotate()
                ip = result.get("new_ip", "unknown")
                status = "OK" if result["success"] else "FAIL"
                log.info(f"Rotation #{result['rotations']}: {result['old_ip']} -> {ip} [{status}]")
                self._log.append(result)
                if self.on_rotation:
                    try:
                        self.on_rotation(result)
                    except Exception:
                        log.exception("Rotation callback failed")
            except Exception as e:
                log.error(f"Rotation failed: {e}")
            if self._stop_event.wait(self.interval):
                break

    def summary(self):
        status = self.rotator.status()
        return {
            "running": self._running,
            "interval": self.interval,
            "total_rotations": status["total_rotations"],
            "total_attempts": status["total_attempts"],
            "current_ip": status["current_ip"],
            "log": self._log[-10:] if self._log else [],
        }
