"""Tests for app/commands/anon.py"""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.commands.anon import (
    _cmd_proxychains, _cmd_macchanger, _cmd_anonsurf,
    _random_mac,
)


class CaptureOutput:
    def __enter__(self):
        import io
        self.buf = io.StringIO()
        self._stdout = sys.stdout
        sys.stdout = self.buf
        return self.buf

    def __exit__(self, *args):
        sys.stdout = self._stdout


class TestAnonCommands:
    def test_proxychains_no_args(self):
        with CaptureOutput() as out:
            _cmd_proxychains([])
        result = out.getvalue()
        assert "usage:" in result

    def test_proxychains_command_not_found(self):
        with CaptureOutput() as out:
            _cmd_proxychains(["__nonexistent_cmd_xyz__", "--help"])
        result = out.getvalue()
        assert "is not recognized" in result or "command not found" in result or "no such file" in result

    def test_macchanger_no_args(self):
        with CaptureOutput() as out:
            _cmd_macchanger([])
        result = out.getvalue()
        assert "MAC" in result or "adapter" in result

    def test_macchanger_show(self):
        with CaptureOutput() as out:
            _cmd_macchanger(["-s"])
        result = out.getvalue()
        assert "MAC" in result

    def test_random_mac_format(self):
        mac = _random_mac()
        parts = mac.split(":")
        assert len(parts) == 6
        for p in parts:
            assert len(p) == 2
            int(p, 16)

    def test_anonsurf_status(self):
        with CaptureOutput() as out:
            _cmd_anonsurf(["status"])
        result = out.getvalue()
        assert "mode" in result.lower()

    def test_anonsurf_start(self):
        import os as _os
        # Clean up any existing file
        env_file = _os.path.join(_os.path.expanduser("~"), ".tether", "proxy.env")
        if _os.path.isfile(env_file):
            _os.remove(env_file)
        with CaptureOutput() as out:
            _cmd_anonsurf(["start"])
        result = out.getvalue()
        assert "STARTED" in result

    def test_anonsurf_stop(self):
        with CaptureOutput() as out:
            _cmd_anonsurf(["stop"])
        result = out.getvalue()
        assert "STOPPED" in result

    def test_anonsurf_no_args(self):
        with CaptureOutput() as out:
            _cmd_anonsurf([])
        result = out.getvalue()
        assert "mode" in result.lower() or "INACTIVE" in result or "usage:" in result

    def test_register_returns(self):
        from app.commands.anon import register
        cmds = {}
        aliases = {}
        register(cmds, aliases)
        assert "proxychains" in cmds
        assert "macchanger" in cmds
        assert "anonsurf" in cmds
