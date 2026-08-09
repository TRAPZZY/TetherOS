import io
import os
import threading
import time
from unittest.mock import patch

import pytest

from app.shell import LineEditor


@pytest.mark.skipif(os.name != "posix", reason="requires a POSIX pseudoterminal")
def test_unix_line_editor_accepts_an_entire_pasted_line_without_stalling():
    import pty

    class Shell:
        @staticmethod
        def _idle_lock_due(_last_activity):
            return False

    master_fd, slave_fd = pty.openpty()
    stdin = os.fdopen(os.dup(slave_fd), "r", encoding="utf-8", buffering=1)
    stdout = io.StringIO()
    editor = LineEditor(Shell())
    result = []

    def read_line():
        result.append(editor._read_unix(editor.prompt_str(), 24))

    try:
        with patch("app.shell.sys.stdin", stdin), patch("app.shell.sys.stdout", stdout):
            reader = threading.Thread(target=read_line, daemon=True)
            reader.start()
            deadline = time.monotonic() + 2
            while ">" not in stdout.getvalue() and time.monotonic() < deadline:
                time.sleep(0.01)
            assert ">" in stdout.getvalue(), "line editor did not publish its prompt"

            # One write intentionally puts the command and Enter in the same
            # kernel buffer, reproducing fast paste and automated serial input.
            os.write(master_fd, b"deck --json\n")
            reader.join(timeout=2)
            if reader.is_alive():
                os.write(master_fd, b"\n")
                reader.join(timeout=1)
            assert not reader.is_alive(), "line editor stalled on buffered input"
            assert result == ["deck --json"]
    finally:
        stdin.close()
        os.close(slave_fd)
        os.close(master_fd)
