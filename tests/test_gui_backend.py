import json
import os
import socket
import struct
import sys
import threading
import time

import pytest

from app.gui_backend import (
    BackendError,
    MAX_REQUEST_BYTES,
    PROTOCOL_VERSION,
    PersistentShellSession,
    SessionLockedError,
    ShellRpcClient,
    ShellRpcServer,
    _parent_pid,
    main as backend_main,
    peer_uid,
)
from app.security import LockResult
from app.shell import TetherShell


class _DesktopLocker:
    def available(self):
        return True

    def lock(self):
        return LockResult(True, True, "desktop", "locked")


def test_persistent_session_keeps_shell_state_across_gui_clients(tmp_path):
    shell = TetherShell(locker=_DesktopLocker())
    session = PersistentShellSession(shell, lock_marker_path=str(tmp_path / "active"))

    first = session.dispatch("execute", {"line": "mkdir persistent"})
    session.dispatch("execute", {"line": "cd persistent"})
    second = session.dispatch("execute", {"line": "pwd"})

    assert first["exit_code"] == 0
    assert second["stdout"].strip().endswith("/persistent")


def test_managed_job_survives_client_reconnect(tmp_path):
    shell = TetherShell(locker=_DesktopLocker())
    session = PersistentShellSession(shell, lock_marker_path=str(tmp_path / "active"))
    command = f'"{sys.executable}" -c "import time; time.sleep(0.2)" &'

    started = session.dispatch("execute", {"line": command})
    # A second dispatch represents a new GTK client using the same backend.
    jobs = session.dispatch("execute", {"line": "jobs"})

    assert started["exit_code"] == 0
    assert "Job 1 started" in started["stdout"]
    assert "1" in jobs["stdout"]
    shell.jobs.shutdown()


def test_command_gate_stays_closed_for_entire_trusted_lock(tmp_path):
    marker = tmp_path / "active"
    session = PersistentShellSession(
        TetherShell(locker=_DesktopLocker()), lock_marker_path=str(marker)
    )

    result = session.dispatch("lock")
    assert result["success"] is True
    assert session.phase == "pending"
    with pytest.raises(SessionLockedError):
        session.dispatch("execute", {"line": "status"})

    marker.write_text("", encoding="ascii")
    session.dispatch("mark-lock-active")
    with pytest.raises(BackendError, match="still active"):
        session.dispatch("unlock")
    with pytest.raises(SessionLockedError):
        session.dispatch("execute", {"line": "status"})
    with pytest.raises(SessionLockedError):
        session.dispatch("state")

    marker.unlink()
    session.dispatch("unlock")
    assert session.dispatch("execute", {"line": "echo authenticated"})["exit_code"] == 0


def test_unlock_is_rejected_without_observing_active_lock(tmp_path):
    session = PersistentShellSession(
        TetherShell(locker=_DesktopLocker()),
        lock_marker_path=str(tmp_path / "active"),
    )
    session.dispatch("lock")
    with pytest.raises(BackendError, match="has not observed"):
        session.dispatch("unlock")


def test_typed_lock_command_atomically_closes_backend_gate(tmp_path):
    session = PersistentShellSession(
        TetherShell(locker=_DesktopLocker()),
        lock_marker_path=str(tmp_path / "active"),
    )

    response = session.dispatch("execute", {"line": "lock"})

    assert response["lock_started"] is True
    assert session.phase == "pending"
    with pytest.raises(SessionLockedError):
        session.dispatch("execute", {"line": "echo too-late"})


def test_linux_peer_uid_comes_from_kernel_credentials(monkeypatch):
    class _Connection:
        def getsockopt(self, level, option, size):
            assert level == socket.SOL_SOCKET
            assert option == socket.SO_PEERCRED
            assert size == struct.calcsize("3i")
            return struct.pack("3i", 4321, 1000, 1000)

    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(socket, "SO_PEERCRED", getattr(socket, "SO_PEERCRED", 17), raising=False)
    assert peer_uid(_Connection()) == 1000


def test_server_rejects_peer_from_another_uid(tmp_path, monkeypatch):
    class _Connection:
        sent = b""

        def sendall(self, data):
            self.sent += data

    shell = TetherShell(locker=_DesktopLocker())
    server = ShellRpcServer(
        PersistentShellSession(shell, lock_marker_path=str(tmp_path / "active")),
        socket_path=str(tmp_path / "backend.sock"),
        expected_uid=1000,
        supervisor_pid=999,
    )
    monkeypatch.setattr("app.gui_backend.peer_uid", lambda _connection: 1001)
    connection = _Connection()

    server._handle(connection)

    response = json.loads(connection.sent)
    assert response["ok"] is False
    assert response["error_type"] == "PermissionError"


class _RpcConnection:
    def __init__(self, action, payload=None):
        self.sent = b""
        self.request = json.dumps({
            "protocol": PROTOCOL_VERSION,
            "action": action,
            "payload": payload or {},
        }).encode("utf-8") + b"\n"

    def recv(self, _size):
        request, self.request = self.request, b""
        return request

    def sendall(self, data):
        self.sent += data


def test_control_rpc_requires_a_direct_child_of_the_live_supervisor(
    tmp_path, monkeypatch
):
    marker = tmp_path / "active"
    session = PersistentShellSession(
        TetherShell(locker=_DesktopLocker()), lock_marker_path=str(marker)
    )
    session.dispatch("lock")
    marker.write_text("", encoding="ascii")
    server = ShellRpcServer(
        session,
        socket_path=str(tmp_path / "backend.sock"),
        expected_uid=1000,
        supervisor_pid=999,
    )
    monkeypatch.setattr("app.gui_backend.peer_uid", lambda _connection: 1000)
    monkeypatch.setattr("app.gui_backend.peer_pid", lambda _connection: 4321)
    monkeypatch.setattr("app.gui_backend.os.getppid", lambda: 999)
    monkeypatch.setattr("app.gui_backend._parent_pid", lambda _pid: 998)
    connection = _RpcConnection("mark-lock-active")

    server._handle(connection)

    response = json.loads(connection.sent)
    assert response["ok"] is False
    assert response["error_type"] == "PermissionError"
    assert session.phase == "pending"


def test_control_rpc_accepts_a_kernel_peer_parented_by_the_live_supervisor(
    tmp_path, monkeypatch
):
    marker = tmp_path / "active"
    session = PersistentShellSession(
        TetherShell(locker=_DesktopLocker()), lock_marker_path=str(marker)
    )
    session.dispatch("lock")
    marker.write_text("", encoding="ascii")
    server = ShellRpcServer(
        session,
        socket_path=str(tmp_path / "backend.sock"),
        expected_uid=1000,
        supervisor_pid=999,
    )
    monkeypatch.setattr("app.gui_backend.peer_uid", lambda _connection: 1000)
    monkeypatch.setattr("app.gui_backend.peer_pid", lambda _connection: 4321)
    monkeypatch.setattr("app.gui_backend.os.getppid", lambda: 999)
    monkeypatch.setattr("app.gui_backend._parent_pid", lambda _pid: 999)
    connection = _RpcConnection("mark-lock-active")

    server._handle(connection)

    response = json.loads(connection.sent)
    assert response["ok"] is True
    assert session.phase == "active"


def test_rpc_fails_closed_after_the_session_supervisor_exits(tmp_path, monkeypatch):
    session = PersistentShellSession(
        TetherShell(locker=_DesktopLocker()),
        lock_marker_path=str(tmp_path / "active"),
    )
    server = ShellRpcServer(
        session,
        socket_path=str(tmp_path / "backend.sock"),
        expected_uid=1000,
        supervisor_pid=999,
    )
    monkeypatch.setattr("app.gui_backend.peer_uid", lambda _connection: 1000)
    monkeypatch.setattr("app.gui_backend.os.getppid", lambda: 1)
    connection = _RpcConnection("execute", {"line": "echo orphaned"})

    server._handle(connection)

    response = json.loads(connection.sent)
    assert response["ok"] is False
    assert response["error_type"] == "PermissionError"


def test_service_start_rejects_a_spoofed_supervisor_pid(tmp_path, monkeypatch):
    monkeypatch.setattr("app.gui_backend.os.getppid", lambda: 1000)
    result = backend_main([
        "--serve",
        "--supervisor-pid", "999",
        "--socket", str(tmp_path / "backend.sock"),
        "--lock-marker", str(tmp_path / "active"),
    ])
    assert result == 2


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="requires /proc")
def test_proc_parent_parser_matches_the_live_process_parent():
    assert _parent_pid(os.getpid()) == os.getppid()


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="requires SO_PEERCRED")
def test_real_unix_socket_round_trip_is_private_and_peer_authenticated(tmp_path):
    runtime = tmp_path / "runtime"
    runtime.mkdir(mode=0o700)
    runtime.chmod(0o700)
    socket_path = runtime / "shell.sock"
    shell = TetherShell(locker=_DesktopLocker())
    server = ShellRpcServer(
        PersistentShellSession(shell, lock_marker_path=str(runtime / "active")),
        socket_path=str(socket_path),
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    deadline = time.monotonic() + 3
    first_client = ShellRpcClient(str(socket_path))
    while time.monotonic() < deadline:
        try:
            if os.stat(socket_path).st_mode & 0o777 == 0o600:
                first_client.request("ping")
                break
        except (BackendError, OSError):
            time.sleep(0.01)
    else:
        raise AssertionError("private authenticated backend did not become ready")

    assert first_client.request("execute", {"line": "mkdir reconnect"})["exit_code"] == 0
    assert first_client.request("execute", {"line": "cd reconnect"})["exit_code"] == 0
    # A new socket client reaches the same in-memory shell instance.
    second_client = ShellRpcClient(str(socket_path))
    assert second_client.request("execute", {"line": "pwd"})["stdout"].strip().endswith(
        "/reconnect"
    )

    server.stop()
    thread.join(timeout=3)
    assert not thread.is_alive()
    shell.jobs.shutdown()


def test_request_parser_rejects_oversized_payload():
    class _Connection:
        def __init__(self):
            self.done = False

        def recv(self, _size):
            if self.done:
                return b""
            self.done = True
            return b"x" * (MAX_REQUEST_BYTES + 1)

    with pytest.raises(BackendError, match="size limit"):
        ShellRpcServer._read_request(_Connection())


def test_request_parser_requires_protocol_version():
    class _Connection:
        def recv(self, _size):
            return json.dumps({"protocol": PROTOCOL_VERSION + 1}).encode() + b"\n"

    with pytest.raises(BackendError, match="Unsupported"):
        ShellRpcServer._read_request(_Connection())
