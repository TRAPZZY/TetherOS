import io
import json
from unittest.mock import patch

from app.deck import DeckState, render_deck
from app.shell import TetherShell


def _state():
    return DeckState(
        version="2.0.0",
        session_user="tether",
        session_uptime_seconds=125,
        lock_ready=True,
        lock_timeout_seconds=600,
        tor_state="RUNNING",
        tor_verified=True,
        current_ip="198.51.100.7",
        rotation_count=4,
        threat_level="LOW",
        running_jobs=2,
        finished_jobs=3,
        command_count=92,
    )


def test_command_deck_renders_bounded_privacy_aware_status():
    rendered = render_deck(_state(), width=70)

    assert "TRAP HUB // COMMAND DECK" in rendered
    assert "PRIVILEGE NON-ROOT" in rendered
    assert "2 running" in rendered
    assert all(len(line) == 70 for line in rendered.splitlines())


def test_command_deck_state_has_machine_readable_json():
    data = json.loads(_state().to_json())
    assert data["session_user"] == "tether"
    assert data["lock_ready"] is True
    assert data["running_jobs"] == 2


def test_shell_deck_json_uses_the_same_state_contract():
    shell = TetherShell()
    with patch("sys.stdout", new=io.StringIO()) as output:
        exit_code = shell._cmd_deck(["--json"])

    data = json.loads(output.getvalue())
    assert exit_code == 0
    assert data["command_count"] == len(shell._commands)
    assert "lock_ready" in data
