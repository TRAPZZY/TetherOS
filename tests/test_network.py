"""Tests for lib.network"""

import os
import sys
from unittest.mock import patch, MagicMock
from lib.network import (
    set_proxy, unset_proxy, get_os,
    check_port, detect_tor_browser, detect_system_tor,
)


class TestNetwork:
    def test_set_proxy(self):
        set_proxy("1.2.3.4:8118", "1.2.3.4:9050")
        assert os.environ.get("HTTP_PROXY") == "http://1.2.3.4:8118"
        assert os.environ.get("SOCKS_PROXY") == "socks5://1.2.3.4:9050"
        unset_proxy()

    def test_unset_proxy(self):
        set_proxy()
        unset_proxy()
        assert os.environ.get("HTTP_PROXY") is None
        assert os.environ.get("SOCKS_PROXY") is None

    def test_get_os(self):
        info = get_os()
        assert "system" in info
        assert "release" in info
        assert "machine" in info

    @patch("socket.socket")
    def test_check_port_open(self, mock_socket_cls):
        mock_sock = MagicMock()
        mock_socket_cls.return_value = mock_sock
        mock_sock.connect.return_value = None
        assert check_port("127.0.0.1", 9050) is True
        mock_sock.connect.assert_called_once_with(("127.0.0.1", 9050))

    @patch("socket.socket")
    def test_check_port_closed(self, mock_socket_cls):
        mock_sock = MagicMock()
        mock_socket_cls.return_value = mock_sock
        mock_sock.connect.side_effect = ConnectionRefusedError
        assert check_port("127.0.0.1", 9050) is False

    @patch("lib.network.check_port")
    def test_detect_tor_browser_found(self, mock_check_port):
        mock_check_port.return_value = True
        result = detect_tor_browser()
        assert result["detected"] is True
        assert result["socks_port"] == 9150

    @patch("lib.network.check_port")
    def test_detect_tor_browser_not_found(self, mock_check_port):
        mock_check_port.return_value = False
        result = detect_tor_browser()
        assert result["detected"] is False

    @patch("lib.network.check_port")
    def test_detect_system_tor_full(self, mock_check_port):
        mock_check_port.return_value = True
        result = detect_system_tor()
        assert result["detected"] is True
        assert result["type"] == "full"
        assert result["socks_port"] == 9050
        assert result["control_port"] == 9051

    @patch("lib.network.check_port")
    def test_detect_system_tor_partial(self, mock_check_port):
        mock_check_port.side_effect = [True, False]
        result = detect_system_tor()
        assert result["detected"] is True
        assert result["type"] == "partial"
        assert result["control_port"] is None

    @patch("lib.network.check_port")
    def test_detect_system_tor_none(self, mock_check_port):
        mock_check_port.return_value = False
        result = detect_system_tor()
        assert result["detected"] is False
