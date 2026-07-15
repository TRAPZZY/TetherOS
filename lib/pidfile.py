"""pidfile.py -- PID file management for Tether OS daemon IPC"""

import os
import signal
import sys
import json

PID_DIR = os.path.join(os.path.expanduser("~"), ".tether")
PID_FILE = os.path.join(PID_DIR, "tetherd.pid")
STATE_FILE = os.path.join(PID_DIR, "tetherd.state")


def ensure_dir():
    os.makedirs(PID_DIR, exist_ok=True)


def write_pid():
    ensure_dir()
    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))


def read_pid():
    try:
        with open(PID_FILE) as f:
            return int(f.read().strip())
    except (FileNotFoundError, ValueError):
        return None


def remove_pid():
    try:
        os.remove(PID_FILE)
    except FileNotFoundError:
        pass
    try:
        os.remove(STATE_FILE)
    except FileNotFoundError:
        pass


def is_running():
    pid = read_pid()
    if not pid:
        return None
    if sys.platform == "win32":
        try:
            import ctypes
            HANDLE = ctypes.windll.kernel32.OpenProcess(
                0x0400, False, pid
            )
            if HANDLE:
                ctypes.windll.kernel32.CloseHandle(HANDLE)
                return pid
            return None
        except Exception:
            return None
    else:
        try:
            os.kill(pid, 0)
            return pid
        except OSError:
            return None


def stop_daemon():
    pid = is_running()
    if not pid:
        return {"stopped": False, "reason": "not running"}
    if sys.platform == "win32":
        try:
            import ctypes
            HANDLE = ctypes.windll.kernel32.OpenProcess(
                0x0001, False, pid
            )
            if HANDLE:
                ctypes.windll.kernel32.TerminateProcess(HANDLE, 0)
                ctypes.windll.kernel32.CloseHandle(HANDLE)
                remove_pid()
                return {"stopped": True, "pid": pid}
            return {"stopped": False, "reason": "access denied"}
        except Exception as e:
            return {"stopped": False, "reason": str(e)}
    else:
        try:
            os.kill(pid, signal.SIGTERM)
            remove_pid()
            return {"stopped": True, "pid": pid}
        except OSError as e:
            return {"stopped": False, "reason": str(e)}


def write_state(state):
    ensure_dir()
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)


def read_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
