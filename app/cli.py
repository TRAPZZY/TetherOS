"""cli.py -- Command-line interface for Tether OS
Unix-style: pipe-friendly JSON, subcommands, composable.
"""

import argparse
import sys
import json
import os
import time

from kernel.rotator import Rotator
from kernel.scheduler import Scheduler
from lib.network import (
    get_os, check_tor, check_tor_service, check_port,
    detect_tor_browser, detect_system_tor,
)
from lib.pidfile import is_running, stop_daemon, read_state
from app.config import load_config
from app.version import __version__


class CLI:
    def __init__(self):
        self.parser = argparse.ArgumentParser(
            prog="tether",
            description="Tether OS -- Automatic IP rotation every 60 seconds",
        )
        self.parser.add_argument(
            "--version", action="version",
            version=f"Tether OS {__version__} by Trapzzy",
        )
        self._sub = self.parser.add_subparsers(dest="command")

        p_start = self._sub.add_parser("start", help="Start IP rotation daemon")
        p_start.add_argument(
            "--interval", type=int, default=60,
            help="Rotation interval in seconds (default: 60)",
        )
        p_start.add_argument(
            "--background", "-b", action="store_true",
            help="Run in background (detach from terminal)",
        )

        p_rotate = self._sub.add_parser(
            "rotate", help="Rotate IP once immediately"
        )

        p_status = self._sub.add_parser("status", help="Show current status")

        p_stop = self._sub.add_parser("stop", help="Stop the daemon")

        p_ip = self._sub.add_parser("ip", help="Show current public IP")

        p_config = self._sub.add_parser("config", help="Print configuration")

        p_check = self._sub.add_parser("check", help="System dependency check")

        p_info = self._sub.add_parser("info", help="System information")

    def run(self, argv=None):
        args = self.parser.parse_args(argv)
        if not args.command:
            self.parser.print_help()
            return 0
        return getattr(self, f"cmd_{args.command}")(args)

    def cmd_rotate(self, args):
        rotator = Rotator()
        result = rotator.rotate()
        print(json.dumps(result, indent=2))
        return 0 if result["success"] else 1

    def cmd_status(self, args):
        pid = is_running()
        if pid:
            state = read_state()
            state["daemon_pid"] = pid
            state["daemon_running"] = True
            print(json.dumps(state, indent=2))
        else:
            local = {"daemon_running": False}
            print(json.dumps(local, indent=2))
        return 0

    def cmd_start(self, args):
        pid = is_running()
        if pid:
            print(f"[TETHER] Daemon already running (PID {pid})")
            return 1
        if args.background:
            try:
                import daemon as daemon_mod
            except ImportError:
                print(
                    "[TETHER] --background requires python-daemon.\n"
                    "  Install: pip install tether-os[background]\n"
                    "  Or run without --background for foreground mode."
                )
                return 1
            with daemon_mod.DaemonContext():
                from app.daemon import main
                main(interval=args.interval)
        else:
            from app.daemon import main
            main(interval=args.interval)
        return 0

    def cmd_stop(self, args):
        result = stop_daemon()
        if result["stopped"]:
            print(f"[TETHER] Daemon stopped (PID {result['pid']})")
        else:
            print(f"[TETHER] Cannot stop: {result['reason']}")
        return 0 if result["stopped"] else 1

    def cmd_ip(self, args):
        from kernel.probe import Probe
        probe = Probe()
        ip = probe.get_current_ip()
        print(ip or "unknown")
        return 0 if ip else 1

    def cmd_config(self, args):
        config = load_config()
        data = {
            "version": __version__,
            "rotation_interval": config.rotation_interval,
            "auto_rotate": config.auto_rotate,
            "tor_host": config.tor_host,
            "tor_socks_port": config.tor_socks_port,
            "tor_control_port": config.tor_control_port,
            "tor_password_configured": bool(config.tor_password),
            "lock_enabled": config.lock_enabled,
            "lock_timeout_seconds": config.lock_timeout_seconds,
        }
        print(json.dumps(data, indent=2))
        return 0

    def cmd_check(self, args):
        tor_bin = check_tor()
        tor_svc = check_tor_service()
        sys_tor = detect_system_tor()
        browser = detect_tor_browser()

        print("=== Tether OS System Check ===")
        print(f"Tor binary:       {'FOUND' if tor_bin else 'MISSING'}")
        print(f"Tor process:      {'RUNNING' if tor_svc else 'STOPPED'}")
        print(f"Port 9050 (SOCKS): {'OPEN' if check_port('127.0.0.1', 9050) else 'CLOSED'}")
        print(f"Port 9051 (CTRL):  {'OPEN' if check_port('127.0.0.1', 9051) else 'CLOSED'}")

        if browser["detected"]:
            print(f"Port 9150 (TBB):   OPEN -- Tor Browser detected")

        print()
        if sys_tor["detected"] and sys_tor["type"] == "full":
            print("[OK] System Tor daemon is fully operational.")
        elif sys_tor["detected"] and sys_tor["type"] == "partial":
            print("[!!] Tor SOCKS port found but control port 9051 is closed.")
            print("     IP rotation (NEWNYM) will NOT work without control port.")
        elif browser["detected"]:
            print("[!!] Tor Browser is running but it does NOT expose the control port.")
            print("     Tether OS needs the Tor Expert Bundle for IP rotation.")
            print()
            print("     Option A -- Install Tor Expert Bundle (recommended):")
            print("       https://www.torproject.org/download/tor/")
            print()
            print("     Option B -- Configure Tor Browser for control port:")
            print('       1. Find torrc in Tor Browser/Data/Tor/torrc')
            print("       2. Add: ControlPort 9051")
            print("       3. Restart Tor Browser")
        else:
            print("[!!] Tor is not running or not configured correctly.")
            print("     Install Tor Expert Bundle: https://www.torproject.org/download/tor/")

        # Check if Tor was installed by our installer but not in PATH
        import os as _os
        installed_tor = _os.path.expanduser("~/.tether/tor/tor.exe")
        installed_tor_nix = _os.path.expanduser("~/.tether/tor/tor")
        start_cmd = _os.path.expanduser("~/.tether/tor/start-tor.cmd")
        start_sh = _os.path.expanduser("~/.tether/tor/start-tor.sh")

        if not tor_bin:
            print()
            if _os.path.isfile(installed_tor) or _os.path.isfile(installed_tor_nix):
                print("[!!] Tor binary installed at ~/.tether/tor/ but not in PATH.")
                if _os.path.isfile(start_cmd):
                    print(f"     Start it: {start_cmd}")
                elif _os.path.isfile(start_sh):
                    print(f"     Start it: {start_sh}")
                print("     Or add to PATH manually.")
            else:
                print("[!!] Tor binary not found. Install Tor Expert Bundle:")
                print("     https://www.torproject.org/download/tor/")
        return 0

    def cmd_info(self, args):
        os_info = get_os()
        print(json.dumps(os_info, indent=2))
        return 0


def main(argv=None):
    cli = CLI()
    return cli.run(argv)


if __name__ == "__main__":
    raise SystemExit(main())
