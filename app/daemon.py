"""daemon.py -- Tether OS daemon (tetherd)
Runs the scheduler in foreground. Manages PID file for IPC.
"""

import sys
import os
import time
import signal
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kernel.scheduler import Scheduler
from lib.network import check_tor, check_port, detect_tor_browser, detect_system_tor
from lib.pidfile import write_pid, remove_pid, write_state
from kernel.probe import Probe

logging.basicConfig(
    level=logging.INFO,
    format="[TETHERD] %(asctime)s %(message)s",
)
log = logging.getLogger("tether.daemon")


def main():
    log.info("Tether OS daemon starting up")

    tor_binary = check_tor()
    sys_tor = detect_system_tor()

    if not tor_binary:
        log.warning("Tor binary not found in PATH, checking running Tor instances...")
        if sys_tor["detected"] and sys_tor["type"] == "full":
            log.info(
                f"Tor daemon already running on ports "
                f"{sys_tor['socks_port']} (SOCKS) / {sys_tor['control_port']} (Ctrl) -- continuing"
            )
        elif sys_tor["detected"] and sys_tor["type"] == "partial":
            log.error(
                "Tor SOCKS port found but control port 9051 is closed.\n"
                "  Tether OS needs control port access to rotate IPs.\n"
                "  Check your Tor configuration has: ControlPort 9051"
            )
            sys.exit(1)
        else:
            browser = detect_tor_browser()
            if browser["detected"]:
                log.error(
                    "Tor Browser detected (port 9150) but not Tor Expert Bundle.\n"
                    "  Tor Browser does not expose the control port.\n"
                    "  Run this to start the correct Tor daemon:\n"
                    f"    {os.path.expanduser('~\.tether\tor\start-tor.cmd')}"
                )
            else:
                log.error(
                    "Tor is not installed or not running.\n"
                    "  1. Download Tor Expert Bundle: https://www.torproject.org/download/tor/\n"
                    "  2. Start Tor with control port enabled (ControlPort 9051)\n"
                    "  3. Run tetherd again"
                )
            sys.exit(1)

    try:
        write_pid()
    except Exception as e:
        log.error(f"Failed to write PID file: {e}")
        sys.exit(1)

    probe = Probe()
    try:
        start_ip = probe.get_ip(use_tor=False)
        log.info(f"Public IP (direct): {start_ip}")
    except Exception:
        log.warning("Could not determine public IP (no internet?)")
        start_ip = "unknown"

    config = {
        "tor_host": "127.0.0.1",
        "tor_control_port": 9051,
        "tor_socks_port": 9050,
    }

    sched = Scheduler(interval=60, config=config)
    sched.start()

    write_state(sched.summary())

    def shutdown(sig, frame):
        log.info("Received shutdown signal")
        sched.stop()
        remove_pid()
        log.info("Tether OS daemon stopped")
        sys.exit(0)

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    try:
        while True:
            write_state(sched.summary())
            time.sleep(5)
    except KeyboardInterrupt:
        shutdown(None, None)


if __name__ == "__main__":
    main()
