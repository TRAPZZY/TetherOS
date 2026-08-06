from unittest.mock import patch
import io
import json

from app.commanding import CommandRegistry, EventBus
from app.shell import TetherShell


def test_registry_remains_mapping_compatible_and_exposes_metadata():
    handler = lambda args: None
    registry = CommandRegistry({"demo": handler})
    descriptor = registry.describe(
        "demo", summary="Demonstration command", category="test", risk="safe"
    )

    assert registry["demo"] is handler
    assert list(registry) == ["demo"]
    assert descriptor.summary == "Demonstration command"
    assert descriptor.category == "test"
    assert registry.complete("de") == ("demo",)


def test_command_execution_emits_correlated_lifecycle_events():
    events = []
    bus = EventBus()
    bus.subscribe(events.append)
    shell = TetherShell(event_bus=bus)

    output, result = shell._run_captured(["echo", "hello"])

    assert "hello" in output
    assert result.ok is True
    assert result.argv == ("echo", "hello")
    assert [event.kind for event in events] == [
        "command.started", "command.completed"
    ]
    assert events[0].command_id == events[1].command_id == result.command_id
    assert events[1].payload["exit_code"] == 0


def test_missing_system_command_has_a_structured_127_result():
    shell = TetherShell()
    with patch("app.shell.subprocess.run", side_effect=FileNotFoundError):
        output, result = shell._run_captured(["definitely-not-installed"])

    assert "command not found" in output
    assert result.exit_code == 127
    assert result.ok is False


def test_event_subscriber_failure_cannot_break_a_command():
    bus = EventBus()
    bus.subscribe(lambda _event: (_ for _ in ()).throw(RuntimeError("observer failed")))
    shell = TetherShell(event_bus=bus)

    _output, result = shell._run_captured(["echo", "still-runs"])

    assert result.ok is True


def test_typed_registry_powers_machine_readable_help():
    shell = TetherShell()
    with patch("sys.stdout", new=io.StringIO()) as output:
        exit_code = shell._cmd_help(["--json"])

    records = json.loads(output.getvalue())
    lock = next(record for record in records if record["name"] == "lock")
    assert exit_code == 0
    assert lock["category"] == "security"
    assert lock["risk"] == "protected"


def test_command_specific_help_resolves_aliases():
    shell = TetherShell()
    with patch("sys.stdout", new=io.StringIO()) as output:
        exit_code = shell._cmd_help(["dashboard"])

    assert exit_code == 0
    assert "DECK" in output.getvalue()
    assert "deck [--json]" in output.getvalue()
