"""Tests for kernel.torctl"""

import pytest
from unittest.mock import patch, MagicMock
from kernel.torctl import TorCtl


class TestTorCtl:
    def test_init(self):
        tc = TorCtl(host="127.0.0.1", port=9051)
        assert tc.host == "127.0.0.1"
        assert tc.port == 9051

    def test_init_default_password(self):
        tc = TorCtl(password=None)
        assert tc.password is None

    @patch("kernel.torctl.socket.create_connection")
    def test_authenticate_no_password(self, mock_conn):
        sock = MagicMock()
        mock_conn.return_value = sock
        sock.recv.return_value = b"250 OK\r\n"

        tc = TorCtl(password=None)
        tc._authenticate(sock)

        sock.sendall.assert_called_once_with(b"AUTHENTICATE\r\n")

    @patch("kernel.torctl.socket.create_connection")
    def test_authenticate_with_password(self, mock_conn):
        sock = MagicMock()
        mock_conn.return_value = sock
        sock.recv.return_value = b"250 OK\r\n"

        tc = TorCtl(password="hunter2")
        tc._authenticate(sock)

        sock.sendall.assert_called_once_with(b'AUTHENTICATE "hunter2"\r\n')

    @patch("kernel.torctl.socket.create_connection")
    def test_authenticate_fails(self, mock_conn):
        sock = MagicMock()
        mock_conn.return_value = sock
        sock.recv.return_value = b"515 Authentication failed\r\n"

        tc = TorCtl(password="wrong")
        with pytest.raises(RuntimeError, match="Tor auth failed"):
            tc._authenticate(sock)

    @patch("kernel.torctl.socket.create_connection")
    def test_newnym_success(self, mock_conn):
        sock = MagicMock()
        mock_conn.return_value = sock
        sock.recv.return_value = b"250 OK\r\n"

        tc = TorCtl()
        result = tc.newnym()

        assert result is True
        sock.sendall.assert_any_call(b"SIGNAL NEWNYM\r\n")

    @patch("kernel.torctl.socket.create_connection")
    def test_newnym_failure(self, mock_conn):
        sock = MagicMock()
        mock_conn.return_value = sock
        sock.recv.side_effect = [
            b"250 OK\r\n",       # auth success
            b"510 Tor is not running\r\n",  # newnym failure
        ]

        tc = TorCtl()
        with pytest.raises(RuntimeError, match="NEWNYM failed"):
            tc.newnym()
