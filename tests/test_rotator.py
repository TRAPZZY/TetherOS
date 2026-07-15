"""Tests for kernel.rotator"""

import pytest
from unittest.mock import patch, MagicMock
from kernel.rotator import Rotator


class TestRotator:
    def test_init(self):
        r = Rotator()
        assert r._rotations == 0
        assert r._last_ip is None

    def test_init_with_config(self):
        cfg = {"tor_host": "10.0.0.1", "tor_control_port": 9999}
        r = Rotator(config=cfg)
        assert r.tor.host == "10.0.0.1"
        assert r.tor.port == 9999

    @patch("kernel.rotator.Rotator.rotate")
    def test_status_after_rotation(self, mock_rotate):
        mock_rotate.return_value = {
            "success": True,
            "old_ip": "1.2.3.4",
            "new_ip": "5.6.7.8",
            "rotations": 1,
        }
        r = Rotator()
        result = r.rotate()
        assert result["success"] is True
        assert result["old_ip"] == "1.2.3.4"
        assert result["new_ip"] == "5.6.7.8"

    @patch("kernel.rotator.TorCtl.newnym")
    @patch("kernel.rotator.Probe.get_current_ip")
    def test_full_rotate_cycle(self, mock_get_ip, mock_newnym):
        mock_get_ip.side_effect = ["10.0.0.1", "10.0.0.2"]
        mock_newnym.return_value = True

        r = Rotator()
        result = r.rotate()

        assert result["success"] is True
        assert result["old_ip"] == "10.0.0.1"
        assert result["new_ip"] == "10.0.0.2"
        assert result["rotations"] == 1
        mock_newnym.assert_called_once()
