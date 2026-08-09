import importlib.util
from pathlib import Path

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
