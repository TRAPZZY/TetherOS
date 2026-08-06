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
from lib.pidfile import write_pid, remove_pid, write_state, is_running
from kernel.probe import Probe
from app.config import load_config
from app.version import __version__

logging.basicConfig(
    level=logging.INFO,
    format="[TETHERD] %(asctime)s %(message)s",
)
log = logging.getLogger("tether.daemon")


def main(interval=None):
    log.info("Tether OS %s daemon starting up", __version__)

    existing_pid = is_running()
    if existing_pid:
        log.error("Daemon already running (PID %s)", existing_pid)
        return 1

    tor_binary = check_tor()
    sys_tor = detect_system_tor()

    if not tor_binary:
        log.warning("Tor binary not found in PATH; a managed running instance is still acceptable")
    if not sys_tor.get("detected") or sys_tor.get("type") != "full":
        if sys_tor.get("type") == "partial":
            log.error(
                "Tor SOCKS port found but control port 9051 is closed.\n"
                "  Tether OS needs control port access to rotate IPs.\n"
                "  Check your Tor configuration has: ControlPort 9051"
            )
        else:
            browser = detect_tor_browser()
            if browser["detected"]:
                log.error(
                    "Tor Browser detected (port 9150) but not Tor Expert Bundle.\n"
                    "  Tor Browser does not expose the control port.\n"
                    "  Run this to start the correct Tor daemon:\n"
                    "    {}".format(os.path.expanduser(r'~\.tether\tor\start-tor.cmd'))
                )
            else:
                log.error(
                    "Tor is not installed or not running.\n"
                    "  1. Download Tor Expert Bundle: https://www.torproject.org/download/tor/\n"
                    "  2. Start Tor with control port enabled (ControlPort 9051)\n"
                    "  3. Run tetherd again"
                )
        return 1

    try:
        write_pid()
    except Exception as e:
        log.error(f"Failed to write PID file: {e}")
        return 1

    runtime_config = load_config()
    sched = Scheduler(
        interval=interval or runtime_config.rotation_interval,
        config=runtime_config.tor_options(),
    )
    sched.start()

    write_state(sched.summary())

    def shutdown(sig, frame):
        log.info("Received shutdown signal")
        sched.stop()
        remove_pid()
        log.info("Tether OS daemon stopped")
        raise SystemExit(0)

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
