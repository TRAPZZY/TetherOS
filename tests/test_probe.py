"""Tests for kernel.probe"""

import pytest
from unittest.mock import patch, MagicMock
from kernel.probe import Probe


class TestProbe:
    def test_valid_ip(self):
        assert Probe._valid_ip("1.2.3.4") is True
        assert Probe._valid_ip("0.0.0.0") is True
        assert Probe._valid_ip("255.255.255.255") is True
        assert Probe._valid_ip("999.999.999.999") is False
        assert Probe._valid_ip("notanip") is False
        assert Probe._valid_ip("") is False
        assert Probe._valid_ip("256.1.2.3") is False

    def test_init(self):
        p = Probe("10.0.0.1", 9999)
        assert p.proxy_host == "10.0.0.1"
        assert p.proxy_port == 9999

    @patch("kernel.probe.urllib.request.urlopen")
    def test_get_ip_direct_success(self, mock_urlopen):
        resp = MagicMock()
        resp.read.return_value = b"203.0.113.42\n"
        mock_urlopen.return_value = resp

        p = Probe()
        ip = p.get_ip(use_tor=False)

        assert ip == "203.0.113.42"

    @patch("kernel.probe.urllib.request.urlopen")
    def test_get_ip_direct_fallback(self, mock_urlopen):
        mock_urlopen.side_effect = [
            Exception("timeout"),
            Exception("timeout"),
            None,
        ]

        def side_effect(url, **kw):
            idx = [u for u in [
                "https://api.ipify.org",
                "https://icanhazip.com",
                "https://ifconfig.me/ip",
            ]].index(url)
            if idx < 2:
                raise Exception("fail")
            resp = MagicMock()
            resp.read.return_value = b"198.51.100.7\n"
            return resp

        mock_urlopen.side_effect = side_effect
        p = Probe()
        ip = p.get_ip(use_tor=False)
        assert ip == "198.51.100.7"

    @patch("kernel.probe.urllib.request.urlopen")
    def test_get_ip_all_services_fail(self, mock_urlopen):
        mock_urlopen.side_effect = Exception("no network")
        p = Probe()
        ip = p.get_ip(use_tor=False)
        assert ip is None
