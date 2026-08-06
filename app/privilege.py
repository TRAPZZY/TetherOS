"""Narrow client for TRAP HUB's boot-image privilege broker."""

from dataclasses import dataclass
import os


ALLOWED_POWER_ACTIONS = frozenset({"poweroff", "reboot"})


@dataclass(frozen=True)
class PrivilegeRequest:
    action: str
    success: bool
    message: str = ""


class PowerBrokerClient:
    def __init__(self, path="/run/tether/control"):
        self.path = path

    def request(self, action: str) -> PrivilegeRequest:
        if action not in ALLOWED_POWER_ACTIONS:
            return PrivilegeRequest(action, False, "Action is not allowlisted.")
        try:
            # O_NONBLOCK is available on TetherOS/Linux but not on every host
            # Python used to test the shared shell (notably Windows).
            fd = os.open(self.path, os.O_WRONLY | getattr(os, "O_NONBLOCK", 0))
            try:
                os.write(fd, f"{action}\n".encode("ascii"))
            finally:
                os.close(fd)
        except OSError as exc:
            return PrivilegeRequest(action, False, str(exc))
        return PrivilegeRequest(action, True)
