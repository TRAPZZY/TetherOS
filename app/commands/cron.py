"""cron.py -- Simple cron-like scheduler for TRAP HUB"""

import time
import threading
import os
import json
import subprocess


CRON_FILE = os.path.join(os.path.expanduser("~"), ".tether", "cron.json")


def _load():
    if os.path.isfile(CRON_FILE):
        try:
            with open(CRON_FILE) as f:
                return json.load(f)
        except:
            pass
    return []


def _save(jobs):
    os.makedirs(os.path.dirname(CRON_FILE), exist_ok=True)
    with open(CRON_FILE, "w") as f:
        json.dump(jobs, f, indent=2)


def _parse_interval(spec):
    spec = spec.lower().strip()
    if spec.endswith("s"):
        return int(spec[:-1])
    elif spec.endswith("m"):
        return int(spec[:-1]) * 60
    elif spec.endswith("h"):
        return int(spec[:-1]) * 3600
    elif spec.endswith("d"):
        return int(spec[:-1]) * 86400
    else:
        try:
            return int(spec)
        except:
            return 60


class CronDaemon:
    def __init__(self, shell=None):
        self.shell = shell
        self._thread = None
        self._running = False
        self._jobs = []

    def start(self):
        if self._running:
            return
        self._running = True
        self._jobs = _load()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    def _run(self):
        while self._running:
            now = time.time()
            for job in self._jobs:
                last = job.get("last_run", 0)
                interval = _parse_interval(job.get("interval", "60s"))
                if now - last >= interval:
                    job["last_run"] = now
                    self._execute_job(job)
            _save(self._jobs)
            time.sleep(5)

    def _execute_job(self, job):
        cmd = job.get("command", "")
        job_id = job.get("id", "?")
        print(f"\n  [CRON] Running job #{job_id}: {cmd}")
        if self.shell:
            self.shell._execute(cmd)


_cron = CronDaemon()


def register(cmds, aliases):
    cmds["cron"] = _cmd_cron


def _usage():
    print("  usage: cron <list|add|del|start|stop> [options]")
    print("  Task scheduler for periodic execution.")
    print("  Examples:")
    print("    cron list")
    print("    cron add rotate 30s")
    print("    cron add 'status' 1m")
    print("    cron del 1")
    print("    cron start")
    print("    cron stop")


def _cmd_cron(args):
    if not args:
        _usage()
        return

    sub = args[0].lower()

    if sub == "list":
        jobs = _load()
        if not jobs:
            print("  No cron jobs scheduled.")
        else:
            print(f"  {'ID':4} {'INTERVAL':12} {'COMMAND':40}")
            print(f"  {'-'*4} {'-'*12} {'-'*40}")
            for i, j in enumerate(jobs, 1):
                print(f"  {i:<4} {j.get('interval', '60s'):12} {j.get('command', ''):40}")

    elif sub == "add" and len(args) >= 3:
        cmd = args[1]
        interval = args[2]
        jobs = _load()
        jobs.append({"id": len(jobs) + 1, "command": cmd, "interval": interval, "last_run": 0})
        _save(jobs)
        print(f"  Added cron job: {cmd} every {interval}")

    elif sub == "del" and len(args) >= 2:
        try:
            idx = int(args[1]) - 1
            jobs = _load()
            if 0 <= idx < len(jobs):
                removed = jobs.pop(idx)
                _save(jobs)
                print(f"  Removed cron job #{args[1]}: {removed.get('command', '')}")
            else:
                print(f"  No job at index {args[1]}")
        except ValueError:
            print("  Usage: cron del <job-number>")

    elif sub == "start":
        _cron.start()
        print("  Cron daemon started.")

    elif sub == "stop":
        _cron.stop()
        print("  Cron daemon stopped.")

    elif sub == "status":
        jobs = _load()
        print(f"  Cron jobs: {len(jobs)} scheduled, running={_cron._running}")
        if _cron._running:
            print(f"  Daemon thread: alive={_cron._thread and _cron._thread.is_alive()}")
    else:
        _usage()
