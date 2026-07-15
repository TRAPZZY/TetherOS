"""session.py -- Session logging for TRAP HUB"""

import os
import time


def _log_path():
    d = os.path.join(os.path.expanduser("~"), ".tether")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "session.log")


def log_cmd(cmd, output=""):
    path = _log_path()
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] $ {cmd}\n")
            if output:
                for line in output.strip().split("\n"):
                    f.write(f"[{ts}]   {line}\n")
            f.write("\n")
    except:
        pass


def view_log(n=50):
    path = _log_path()
    if not os.path.isfile(path):
        return ["(no session log yet)"]
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        return lines[-n:]
    except:
        return ["(error reading log)"]
