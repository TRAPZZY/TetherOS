"""Trusted session-lock integration for TRAP HUB.

The Python UI never verifies a password.  It delegates locking to the host
operating system so authentication remains outside the process being locked.
"""

from dataclasses import dataclass
import os
import re
import signal
import shutil
import subprocess
import sys
from typing import Mapping, Optional

DESKTOP_LOCK_SIGNAL = getattr(signal, "SIGUSR1", 10)


@dataclass(frozen=True)
class LockResult:
    available: bool
    success: bool
    backend: Optional[str]
    message: str = ""


class SessionLocker:
    """Select and invoke a trusted lock backend without a command shell."""

    def __init__(
        self,
        *,
        environ: Optional[Mapping[str, str]] = None,
        os_name: Optional[str] = None,
        platform: Optional[str] = None,
        which=shutil.which,
        runner=subprocess.run,
        tty_name=None,
        desktop_pid_file="/run/user/1000/trap-hub-desktop.pid",
        desktop_request_file="/run/user/1000/trap-hub-lock",
    ):
        self._environ = os.environ if environ is None else environ
        self._os_name = os.name if os_name is None else os_name
        self._platform = sys.platform if platform is None else platform
        self._which = which
        self._runner = runner
        self._tty_name = tty_name or self._current_tty
        self._desktop_pid_file = desktop_pid_file
        self._desktop_request_file = desktop_request_file

    @staticmethod
    def _current_tty():
        try:
            return os.ttyname(sys.stdin.fileno())
        except (AttributeError, OSError, ValueError):
            return None

    def _boot_session_requires_logout(self):
        if self._environ.get("TETHER_BOOT_IMAGE") != "1":
            return False
        tty_path = self._tty_name()
        return bool(tty_path) and re.fullmatch(r"/dev/tty\d+", tty_path) is None

    def _desktop_supervisor_pid(self):
        try:
            with open(self._desktop_pid_file, "r", encoding="ascii") as handle:
                pid = int(handle.read().strip())
            if pid <= 1:
                return None
            os.kill(pid, 0)
            return pid
        except (OSError, TypeError, ValueError):
            return None

    def _request_desktop_lock(self):
        pid = self._desktop_supervisor_pid()
        if pid is None:
            return LockResult(
                available=False,
                success=False,
                backend="desktop",
                message="The trusted desktop lock supervisor is unavailable.",
            )
        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
        flags |= getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(self._desktop_request_file, flags, 0o600)
            os.close(descriptor)
            os.kill(pid, DESKTOP_LOCK_SIGNAL)
        except OSError as exc:
            return LockResult(True, False, "desktop", str(exc))
        return LockResult(
            available=True,
            success=True,
            backend="desktop",
            message="The desktop was handed to the trusted TetherOS locker.",
        )

    def _backend(self):
        if self._environ.get("TETHER_BOOT_IMAGE") == "1":
            if self._environ.get("TETHER_DESKTOP") == "1":
                return ("desktop", None) if self._desktop_supervisor_pid() else (None, None)
            if self._boot_session_requires_logout():
                return "logout", []
            executable = self._which("vlock")
            return ("vlock", [executable, "-a"]) if executable else (None, None)

        if self._os_name == "nt":
            executable = self._which("rundll32.exe") or self._which("rundll32")
            command = [executable, "user32.dll,LockWorkStation"] if executable else None
            return ("windows", command) if command else (None, None)

        if self._platform == "darwin":
            executable = self._which("pmset")
            return ("macos", [executable, "displaysleepnow"]) if executable else (None, None)

        executable = self._which("loginctl")
        if executable:
            return "loginctl", [executable, "lock-session"]
        executable = self._which("xdg-screensaver")
        if executable:
            return "xdg-screensaver", [executable, "lock"]
        return None, None

    def available(self) -> bool:
        backend, command = self._backend()
        return backend in {"logout", "desktop"} or bool(command)

    def lock(self) -> LockResult:
        backend, command = self._backend()
        if backend == "desktop":
            return self._request_desktop_lock()
        if backend == "logout":
            return LockResult(
                available=True,
                success=True,
                backend="logout",
                message="Serial session ended; standard login will require the password.",
            )
        if not command:
            return LockResult(
                available=False,
                success=False,
                backend=None,
                message="No trusted operating-system lock service is available.",
            )
        try:
            completed = self._runner(command, check=False, shell=False)
        except OSError as exc:
            return LockResult(True, False, backend, str(exc))
        success = completed.returncode == 0
        message = "" if success else f"Lock service exited with status {completed.returncode}."
        return LockResult(True, success, backend, message)
