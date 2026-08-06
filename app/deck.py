"""Dependency-free TRAP HUB Command Deck renderer."""

from dataclasses import asdict, dataclass
import json
from typing import Optional


@dataclass(frozen=True)
class DeckState:
    version: str
    session_user: str
    session_uptime_seconds: int
    lock_ready: bool
    lock_timeout_seconds: int
    tor_state: str
    tor_verified: bool
    current_ip: Optional[str]
    rotation_count: int
    threat_level: str
    running_jobs: int
    finished_jobs: int
    command_count: int

    def to_json(self):
        return json.dumps(asdict(self), indent=2, sort_keys=True)


def _clip(value, width):
    text = str(value)
    return text if len(text) <= width else text[: max(0, width - 1)] + "~"


def render_deck(state: DeckState, width=78):
    width = max(54, min(int(width), 120))
    inner = width - 4
    line = "+" + "-" * (width - 2) + "+"

    def row(left="", right=""):
        left_width = inner // 2
        right_width = inner - left_width
        return (
            "| " + _clip(left, left_width).ljust(left_width) +
            _clip(right, right_width).rjust(right_width) + " |"
        )

    protected = "VERIFIED" if state.tor_verified else "UNVERIFIED"
    lock_state = "READY" if state.lock_ready else "UNAVAILABLE"
    uptime = f"{state.session_uptime_seconds // 60}m {state.session_uptime_seconds % 60}s"
    ip = state.current_ip or "not established"
    return "\n".join([
        line,
        row(f"TRAP HUB // COMMAND DECK v{state.version}", "SESSION ACTIVE"),
        line,
        row(f"OPERATOR  {state.session_user}", f"UPTIME  {uptime}"),
        row(f"LOCK      {lock_state}", f"AUTO     {state.lock_timeout_seconds}s"),
        line,
        row(f"TOR       {state.tor_state}", f"ROUTE    {protected}"),
        row(f"EXIT IP   {ip}", f"ROTATIONS {state.rotation_count}"),
        row(f"RISK      {state.threat_level}", "PRIVILEGE NON-ROOT"),
        line,
        row(f"JOBS      {state.running_jobs} running", f"{state.finished_jobs} finished"),
        row(f"COMMANDS  {state.command_count} registered", "lock  help  jobs  status"),
        line,
    ])
