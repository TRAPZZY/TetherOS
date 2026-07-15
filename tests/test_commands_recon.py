"""Tests for app/commands/recon.py"""

import sys
import os
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.commands.recon import (
    _cmd_whois, _cmd_nmap, _cmd_dnsrecon, _cmd_gobuster,
    _cmd_theharvester, _cmd_whatweb,
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


class TestReconCommands:
    def test_nmap_no_args(self):
        with CaptureOutput() as out:
            _cmd_nmap([])
        assert "usage:" in out.getvalue()

    def test_nmap_localhost(self):
        with CaptureOutput() as out:
            _cmd_nmap(["-p", "22,80", "127.0.0.1"])
        assert "Scanning" in out.getvalue()

    def test_nmap_with_tor_flag(self):
        with CaptureOutput() as out:
            _cmd_nmap(["--tor", "127.0.0.1"])
        assert "via Tor" in out.getvalue()

    def test_dnsrecon_no_args(self):
        with CaptureOutput() as out:
            _cmd_dnsrecon([])
        assert "usage:" in out.getvalue()

    @patch("app.commands.recon._try_resolve")
    def test_dnsrecon_lookup(self, mock_resolve):
        mock_resolve.return_value = "93.184.216.34"
        with CaptureOutput() as out:
            _cmd_dnsrecon(["-d", "example.com", "-t", "std"])
        assert "DNS Reconnaissance" in out.getvalue()

    def test_gobuster_no_args(self):
        with CaptureOutput() as out:
            _cmd_gobuster([])
        assert "usage:" in out.getvalue()

    @patch("urllib.request.urlopen")
    def test_gobuster_with_url(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.status = 404
        mock_resp.read.return_value = b""
        mock_urlopen.return_value = mock_resp

        with CaptureOutput() as out:
            _cmd_gobuster(["-u", "http://localhost:9999"])
        assert "brute-forcing" in out.getvalue().lower()

    def test_theharvester_no_args(self):
        with CaptureOutput() as out:
            _cmd_theharvester([])
        assert "usage:" in out.getvalue()

    @patch("app.commands.recon._try_resolve")
    def test_theharvester_domain(self, mock_resolve):
        mock_resolve.return_value = "93.184.216.34"
        with CaptureOutput() as out:
            _cmd_theharvester(["-d", "example.com", "-b", "dns"])
        assert "OSINT" in out.getvalue()

    def test_whatweb_no_args(self):
        with CaptureOutput() as out:
            _cmd_whatweb([])
        assert "usage:" in out.getvalue()

    def test_whois_no_args(self):
        with CaptureOutput() as out:
            _cmd_whois([])
        assert "usage:" in out.getvalue()

    def test_register_returns(self):
        from app.commands.recon import register
        cmds, aliases = {}, {}
        register(cmds, aliases)
        for name in ("nmap", "dnsrecon", "gobuster", "theharvester", "whatweb", "whois"):
            assert name in cmds
