"""Authenticated local RPC service for the persistent Desktop shell session.

The GTK process is intentionally disposable: Weston stops it while vlock owns
the console, then starts a fresh client after authentication.  This service
owns the TetherShell instance and its JobManager for the full login session so
shell state and managed subprocesses survive that compositor restart.
"""

from dataclasses import asdict, replace
import argparse
import json
import os
from pathlib import Path
import signal
import socket
import stat
import struct
import sys
import threading
import time

from app.deck import DeckState
from app.gui import CommandDeckController, GuiCommandResponse
from app.security import LockResult


PROTOCOL_VERSION = 1
MAX_REQUEST_BYTES = 128 * 1024
MAX_RESPONSE_BYTES = 2 * 1024 * 1024


class BackendError(RuntimeError):
    """A local shell backend request failed."""


class SessionLockedError(BackendError):
    """Command execution was rejected because the session is locked."""


def default_runtime_dir():
    configured = os.environ.get("XDG_RUNTIME_DIR")
    if configured:
        return configured
    if not hasattr(os, "geteuid"):
        raise BackendError("A secure per-user runtime directory is unavailable.")
    return f"/run/user/{os.geteuid()}"


def default_socket_path():
    return os.path.join(default_runtime_dir(), "trap-hub-shell.sock")


def default_lock_marker_path():
    return os.path.join(default_runtime_dir(), "trap-hub-lock.active")


def _effective_uid():
    if not hasattr(os, "geteuid"):
        raise BackendError("The Desktop shell service requires Linux user credentials.")
    return os.geteuid()


def _validate_runtime_dir(path, expected_uid):
    info = os.stat(path, follow_symlinks=False)
    if not stat.S_ISDIR(info.st_mode):
        raise BackendError(f"Runtime path is not a directory: {path}")
    if info.st_uid != expected_uid:
        raise BackendError(f"Runtime directory is not owned by uid {expected_uid}: {path}")
    if info.st_mode & 0o077:
        raise BackendError(f"Runtime directory permissions are not private: {path}")


def _validate_socket(path, expected_uid):
    info = os.stat(path, follow_symlinks=False)
    if not stat.S_ISSOCK(info.st_mode):
        raise BackendError(f"Backend endpoint is not a Unix socket: {path}")
    if info.st_uid != expected_uid:
        raise BackendError(f"Backend socket is not owned by uid {expected_uid}: {path}")
    if stat.S_IMODE(info.st_mode) & 0o077:
        raise BackendError(f"Backend socket permissions are not private: {path}")


def peer_uid(connection):
    """Return the Linux uid authenticated by the kernel for this connection."""
    if not sys.platform.startswith("linux") or not hasattr(socket, "SO_PEERCRED"):
        raise PermissionError("SO_PEERCRED is required for Desktop shell RPC")
    size = struct.calcsize("3i")
    credentials = connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, size)
    _pid, uid, _gid = struct.unpack("3i", credentials)
    return uid


def peer_pid(connection):
    """Return the kernel-authenticated process id for a Unix peer."""
    if not sys.platform.startswith("linux") or not hasattr(socket, "SO_PEERCRED"):
        raise PermissionError("SO_PEERCRED is required for Desktop shell RPC")
    size = struct.calcsize("3i")
    credentials = connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, size)
    pid, _uid, _gid = struct.unpack("3i", credentials)
    return pid


def _parent_pid(pid):
    try:
        stat_line = Path(f"/proc/{int(pid)}/stat").read_text(encoding="ascii")
        fields = stat_line[stat_line.rfind(")") + 2:].split()
        return int(fields[1])
    except (OSError, ValueError, IndexError) as exc:
        raise PermissionError("Unable to authenticate backend control process.") from exc


class PersistentShellSession:
    """Own and serialize one TetherShell across any number of GUI clients."""

    def __init__(self, shell, *, lock_marker_path):
        self.shell = shell
        self.controller = CommandDeckController(shell)
        self.lock_marker_path = lock_marker_path
        self._phase = "unlocked"
        self._lock = threading.RLock()

    @property
    def phase(self):
        with self._lock:
            return self._phase

    def _marker_active(self):
        return os.path.isfile(self.lock_marker_path)

    def _require_unlocked(self):
        if self._phase != "unlocked" or self._marker_active():
            raise SessionLockedError("The Desktop session is locked; command RPC is disabled.")

    def _begin_lock(self):
        # Close the command gate before asking the supervisor to tear down
        # Weston, eliminating a post-request execution race.
        self._phase = "pending"
        result = self.controller.lock()
        if not result.success:
            self._phase = "unlocked"
        return result

    def dispatch(self, action, payload=None):
        payload = payload or {}
        with self._lock:
            if action == "ping":
                return {"protocol": PROTOCOL_VERSION, "phase": self._phase}
            if action == "state":
                self._require_unlocked()
                return asdict(self.controller.state())
            if action == "execute":
                self._require_unlocked()
                response = self.controller.execute(str(payload.get("line", "")))
                if response.lock_requested:
                    result = self._begin_lock()
                    if result.success:
                        response = replace(response, lock_started=True)
                    else:
                        response = replace(
                            response,
                            stdout=response.stdout + f"[lock failed: {result.message}]\n",
                            exit_code=1,
                            lock_requested=False,
                        )
                return asdict(response)
            if action == "lock":
                self._require_unlocked()
                return asdict(self._begin_lock())
            if action == "mark-lock-active":
                if self._phase != "pending" or not self._marker_active():
                    raise BackendError("Lock activation did not follow a valid pending request.")
                self._phase = "active"
                return {"phase": self._phase}
            if action == "unlock":
                if self._phase != "active":
                    raise BackendError("The service has not observed an active trusted lock.")
                if self._marker_active():
                    raise BackendError("The trusted lock is still active.")
                self._phase = "unlocked"
                return {"phase": self._phase}
            raise BackendError(f"Unknown backend action: {action}")


class ShellRpcServer:
    """Single-session Unix-domain server with kernel-authenticated peers."""

    def __init__(
        self, session, *, socket_path, expected_uid=None, supervisor_pid=None
    ):
        self.session = session
        self.socket_path = socket_path
        self.expected_uid = _effective_uid() if expected_uid is None else expected_uid
        self.supervisor_pid = supervisor_pid
        self._listener = None
        self._stopping = threading.Event()

    def _prepare_path(self):
        parent = os.path.dirname(self.socket_path)
        _validate_runtime_dir(parent, self.expected_uid)
        try:
            existing = os.stat(self.socket_path, follow_symlinks=False)
        except FileNotFoundError:
            return
        if not stat.S_ISSOCK(existing.st_mode) or existing.st_uid != self.expected_uid:
            raise BackendError(f"Refusing to replace unsafe backend endpoint: {self.socket_path}")
        os.unlink(self.socket_path)

    @staticmethod
    def _read_request(connection):
        data = bytearray()
        while b"\n" not in data:
            chunk = connection.recv(min(65536, MAX_REQUEST_BYTES + 1 - len(data)))
            if not chunk:
                break
            data.extend(chunk)
            if len(data) > MAX_REQUEST_BYTES:
                raise BackendError("Backend request exceeds the size limit.")
        if not data:
            raise BackendError("Empty backend request.")
        line, separator, trailing = bytes(data).partition(b"\n")
        if not separator or trailing:
            raise BackendError("Backend requests must contain exactly one JSON line.")
        try:
            request = json.loads(line.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise BackendError("Malformed backend request.") from exc
        if not isinstance(request, dict) or request.get("protocol") != PROTOCOL_VERSION:
            raise BackendError("Unsupported backend protocol.")
        return request

    @staticmethod
    def _write_response(connection, response):
        encoded = json.dumps(response, separators=(",", ":")).encode("utf-8") + b"\n"
        if len(encoded) > MAX_RESPONSE_BYTES:
            encoded = json.dumps({
                "ok": False,
                "error": "Backend response exceeds the size limit.",
                "error_type": "BackendError",
            }, separators=(",", ":")).encode("utf-8") + b"\n"
        connection.sendall(encoded)

    def _handle(self, connection):
        try:
            if peer_uid(connection) != self.expected_uid:
                raise PermissionError("Backend peer uid does not match the session owner.")
            if self.supervisor_pid is not None and os.getppid() != self.supervisor_pid:
                raise PermissionError("Backend session supervisor is no longer live.")
            request = self._read_request(connection)
            if request.get("action") in {"mark-lock-active", "unlock"}:
                if self.supervisor_pid is None:
                    raise PermissionError("Backend control supervisor is unavailable.")
                if _parent_pid(peer_pid(connection)) != self.supervisor_pid:
                    raise PermissionError("Backend control peer is not the session supervisor.")
            result = self.session.dispatch(request.get("action"), request.get("payload"))
            response = {"ok": True, "result": result}
        except Exception as exc:  # Return a controlled error across the trust boundary.
            response = {
                "ok": False,
                "error": str(exc) or exc.__class__.__name__,
                "error_type": exc.__class__.__name__,
            }
        try:
            self._write_response(connection, response)
        except OSError:
            # A client that disconnects before reading its response must not
            # terminate the long-lived session service or its managed jobs.
            return

    def serve_forever(self):
        self._prepare_path()
        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._listener = listener
        try:
            listener.bind(self.socket_path)
            os.chmod(self.socket_path, 0o600)
            listener.listen(4)
            listener.settimeout(1.0)
            while not self._stopping.is_set():
                if self.supervisor_pid is not None and os.getppid() != self.supervisor_pid:
                    # The authenticated login supervisor is the lifetime
                    # boundary.  An orphaned service must not survive until
                    # its recorded PID can be recycled by the kernel.
                    break
                try:
                    connection, _address = listener.accept()
                except socket.timeout:
                    continue
                with connection:
                    connection.settimeout(10.0)
                    self._handle(connection)
        finally:
            listener.close()
            self._listener = None
            try:
                os.unlink(self.socket_path)
            except FileNotFoundError:
                pass

    def stop(self):
        self._stopping.set()


class ShellRpcClient:
    def __init__(self, socket_path=None, *, timeout=10.0, expected_uid=None):
        self.socket_path = socket_path or default_socket_path()
        self.timeout = timeout
        self.expected_uid = _effective_uid() if expected_uid is None else expected_uid

    def request(self, action, payload=None):
        _validate_socket(self.socket_path, self.expected_uid)
        request = json.dumps({
            "protocol": PROTOCOL_VERSION,
            "action": action,
            "payload": payload or {},
        }, separators=(",", ":")).encode("utf-8") + b"\n"
        connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        connection.settimeout(self.timeout)
        try:
            connection.connect(self.socket_path)
            connection.sendall(request)
            response = bytearray()
            while b"\n" not in response:
                chunk = connection.recv(min(65536, MAX_RESPONSE_BYTES + 1 - len(response)))
                if not chunk:
                    break
                response.extend(chunk)
                if len(response) > MAX_RESPONSE_BYTES:
                    raise BackendError("Backend response exceeds the size limit.")
        finally:
            connection.close()
        line, separator, trailing = bytes(response).partition(b"\n")
        if not separator or trailing:
            raise BackendError("Malformed backend response.")
        try:
            decoded = json.loads(line.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise BackendError("Malformed backend response.") from exc
        if not decoded.get("ok"):
            message = decoded.get("error", "Backend request failed.")
            if decoded.get("error_type") == "SessionLockedError":
                raise SessionLockedError(message)
            raise BackendError(message)
        return decoded.get("result")


class RemoteCommandDeckController:
    """CommandDeckController-compatible facade used by the GTK process."""

    def __init__(self, client):
        self.client = client

    def state(self):
        return DeckState(**self.client.request("state"))

    def execute(self, line):
        return GuiCommandResponse(**self.client.request("execute", {"line": line}))

    def lock(self):
        return LockResult(**self.client.request("lock"))


def _control(client, action):
    client.request(action)
    return 0


def _wait_ready(client, timeout):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            client.request("ping")
            return 0
        except (BackendError, OSError):
            time.sleep(0.1)
    print("TRAP HUB persistent shell service did not become ready.", file=sys.stderr)
    return 1


def main(argv=None):
    parser = argparse.ArgumentParser(description="TRAP HUB persistent Desktop shell service")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--serve", action="store_true")
    mode.add_argument("--ping", action="store_true")
    mode.add_argument("--mark-lock-active", action="store_true")
    mode.add_argument("--unlock", action="store_true")
    mode.add_argument("--wait-ready", type=float, metavar="SECONDS")
    parser.add_argument("--socket", default=None)
    parser.add_argument("--lock-marker", default=None)
    parser.add_argument("--supervisor-pid", type=int)
    args = parser.parse_args(argv)
    socket_path = args.socket or default_socket_path()
    lock_marker = args.lock_marker or default_lock_marker_path()

    if args.serve:
        from app.shell import TetherShell

        if (
            args.supervisor_pid is None
            or args.supervisor_pid <= 1
            or args.supervisor_pid != os.getppid()
        ):
            print(
                "TRAP HUB shell service requires its live Desktop supervisor PID.",
                file=sys.stderr,
            )
            return 2
        shell = TetherShell()
        server = ShellRpcServer(
            PersistentShellSession(shell, lock_marker_path=lock_marker),
            socket_path=socket_path,
            supervisor_pid=args.supervisor_pid,
        )
        previous_handlers = {}

        def request_stop(_signum, _frame):
            server.stop()

        for signum in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
            previous_handlers[signum] = signal.signal(signum, request_stop)
        try:
            server.serve_forever()
        finally:
            for signum, previous in previous_handlers.items():
                signal.signal(signum, previous)
            shell.jobs.shutdown()
        return 0
    client = ShellRpcClient(socket_path)
    if args.wait_ready is not None:
        return _wait_ready(client, max(0.0, args.wait_ready))
    if args.mark_lock_active:
        return _control(client, "mark-lock-active")
    if args.unlock:
        return _control(client, "unlock")
    return _control(client, "ping")


if __name__ == "__main__":
    raise SystemExit(main())
