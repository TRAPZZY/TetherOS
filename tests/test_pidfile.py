"""Tests for lib.pidfile"""

import os
import pytest
from unittest.mock import patch
from lib.pidfile import (
    write_pid, read_pid, remove_pid, is_running,
    write_state, read_state, PID_DIR, PID_FILE, STATE_FILE,
)


class TestPidFile:
    def setup_method(self):
        remove_pid()

    def teardown_method(self):
        remove_pid()

    def test_write_and_read_pid(self):
        write_pid()
        pid = read_pid()
        assert pid == os.getpid()

    def test_read_pid_no_file(self):
        remove_pid()
        assert read_pid() is None

    def test_read_pid_invalid_content(self):
        os.makedirs(PID_DIR, exist_ok=True)
        with open(PID_FILE, "w") as f:
            f.write("not-a-number")
        assert read_pid() is None

    def test_write_and_read_state(self):
        state = {"current_ip": "1.2.3.4", "total_rotations": 42}
        write_state(state)
        loaded = read_state()
        assert loaded == state

    def test_read_state_no_file(self):
        remove_pid()
        assert read_state() == {}
