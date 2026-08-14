import importlib.util
from pathlib import Path
import re

import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "qemu_smoke", ROOT / "scripts" / "qemu-smoke.py"
)
QEMU_SMOKE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(QEMU_SMOKE)


def test_qemu_keyboard_encoder_supports_the_session_password():
    encoded = [
        QEMU_SMOKE._key_name(character)
        for character in QEMU_SMOKE.SESSION_PASSWORD + QEMU_SMOKE.INVALID_PASSWORD
    ]
    assert encoded[0] == "shift-t"
    assert "minus" in encoded
    assert encoded[-1] == "shift-1"


def test_framebuffer_validation_accepts_a_nonblank_ppm(tmp_path):
    screenshot = tmp_path / "desktop.ppm"
    screenshot.write_bytes(b"P6\n64 32\n255\n" + bytes(range(256)) * 24)
    QEMU_SMOKE._validate_framebuffer(screenshot)


def test_framebuffer_validation_rejects_a_blank_ppm(tmp_path):
    screenshot = tmp_path / "desktop.ppm"
    screenshot.write_bytes(b"P6\n64 32\n255\n" + b"\x00" * 6144)
    with pytest.raises(RuntimeError, match="blank"):
        QEMU_SMOKE._validate_framebuffer(screenshot)


def test_boot_budget_reports_elapsed_time_and_rejects_regressions():
    assert QEMU_SMOKE._enforce_boot_budget(10, 20, now=25) == 15
    with pytest.raises(RuntimeError, match="boot-to-shell"):
        QEMU_SMOKE._enforce_boot_budget(10, 20, now=31)


def test_shell_prompt_pattern_waits_for_the_interactive_prompt():
    rendered = "\x1b[23;1H\x1b[2K\x1b[36m>\x1b[0m "
    assert re.search(QEMU_SMOKE.SHELL_PROMPT_PATTERN, rendered)
    assert re.search(
        QEMU_SMOKE.SCHEDULER_READY_PATTERN,
        "Scheduler started -- rotating IP every 60s",
    )


def test_serial_lines_are_paced_before_their_terminator(monkeypatch):
    calls = []

    class Child:
        def send(self, value):
            calls.append(("send", value))

    monkeypatch.setattr(
        QEMU_SMOKE.time,
        "sleep",
        lambda delay: calls.append(("sleep", delay)),
    )

    QEMU_SMOKE._send_serial_line(Child(), "go", delay=0.01)
    assert calls == [
        ("send", "g"),
        ("sleep", 0.01),
        ("send", "o"),
        ("sleep", 0.01),
        ("send", "\n"),
    ]


@pytest.mark.parametrize("newline", ["\n", "\r\n", "\r\r\n"])
def test_console_line_pattern_accepts_terminal_newline_translation(newline):
    rendered = f"cat /etc/tether-edition\x1b[22;1Hcore{newline}next"
    assert re.search(QEMU_SMOKE._console_line_pattern("core"), rendered)


def test_guest_path_pattern_accepts_nested_pty_translation_and_captures_state():
    rendered = "probe expression\x1b[22;1HGUI_PRESENT\r\r\n"
    match = re.search(QEMU_SMOKE._guest_path_pattern("GUI"), rendered)
    assert match
    assert match.group(1) == "PRESENT"


def test_failed_smoke_captures_a_diagnostic_framebuffer(monkeypatch, tmp_path):
    captured = []

    class Child:
        logfile_read = None

        def expect(self, _pattern, **_kwargs):
            raise RuntimeError("guest failed")

        def close(self, force=False):
            assert force is True

    class Pexpect:
        @staticmethod
        def spawn(*_args, **_kwargs):
            return Child()

    monkeypatch.setitem(__import__("sys").modules, "pexpect", Pexpect)
    monkeypatch.setattr(QEMU_SMOKE.shutil, "which", lambda _name: "/usr/bin/qemu")
    monkeypatch.setattr(
        QEMU_SMOKE,
        "_capture_framebuffer",
        lambda monitor, screenshot: captured.append((monitor, screenshot)),
    )

    iso = tmp_path / "test.iso"
    iso.write_bytes(b"not needed by the mocked QEMU")
    screenshot = tmp_path / "failure.ppm"
    with pytest.raises(RuntimeError, match="QEMU smoke failed"):
        QEMU_SMOKE.run_smoke(iso, screenshot_path=screenshot)

    assert len(captured) == 1
    assert captured[0][1] == screenshot
