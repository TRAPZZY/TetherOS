"""Tests for kernel.scheduler"""

import pytest
from unittest.mock import patch, MagicMock
from kernel.scheduler import Scheduler


class TestScheduler:
    def test_init(self):
        s = Scheduler(interval=30)
        assert s.interval == 30
        assert s._running is False

    def test_start_creates_thread(self):
        s = Scheduler(interval=9999)
        result = s.start()
        assert result["status"] == "started"
        assert s._running is True
        assert s._thread is not None
        s.stop()

    def test_start_stop_cycle(self):
        s = Scheduler(interval=9999)
        s.start()
        assert s._running is True
        result = s.stop()
        assert result["status"] == "stopped"
        assert s._running is False

    def test_summary_before_start(self):
        s = Scheduler(interval=60)
        summary = s.summary()
        assert summary["running"] is False
        assert summary["total_rotations"] == 0
