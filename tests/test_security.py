import io
from types import SimpleNamespace
from unittest.mock import patch

from app.privilege import PowerBrokerClient
from app.security import DESKTOP_LOCK_SIGNAL, SessionLocker
from app.shell import TetherShell


def test_boot_image_locker_requires_vlock_all_and_never_uses_a_shell():
    calls = []

    def runner(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0)

    locker = SessionLocker(
        environ={"TETHER_BOOT_IMAGE": "1"},
        os_name="posix",
        platform="linux",
        which=lambda name: "/usr/bin/vlock" if name == "vlock" else None,
        runner=runner,
    )

    result = locker.lock()

    assert result.success is True
    assert result.backend == "vlock"
    assert calls == [(["/usr/bin/vlock", "-a"], {"check": False, "shell": False})]


def test_boot_image_locker_fails_closed_without_vlock():
    locker = SessionLocker(
        environ={"TETHER_BOOT_IMAGE": "1"},
        os_name="posix",
        platform="linux",
        which=lambda _name: None,
    )

    result = locker.lock()

    assert result.available is False
    assert result.success is False


def test_serial_boot_session_locks_by_returning_to_authenticated_login():
    locker = SessionLocker(
        environ={"TETHER_BOOT_IMAGE": "1"},
        os_name="posix",
        platform="linux",
        which=lambda _name: None,
        tty_name=lambda: "/dev/ttyS0",
    )

    result = locker.lock()

    assert locker.available() is True
    assert result.success is True
    assert result.backend == "logout"


def test_desktop_lock_hands_session_to_supervisor(tmp_path):
    pid_file = tmp_path / "desktop.pid"
    request_file = tmp_path / "lock"
    pid_file.write_text("4321", encoding="ascii")
    calls = []

    def kill(pid, sig):
        calls.append((pid, sig))

    locker = SessionLocker(
        environ={"TETHER_BOOT_IMAGE": "1", "TETHER_DESKTOP": "1"},
        desktop_pid_file=str(pid_file),
        desktop_request_file=str(request_file),
    )

    with patch("app.security.os.kill", side_effect=kill):
        result = locker.lock()

    assert result.success is True
    assert result.backend == "desktop"
    assert request_file.exists()
    assert calls[0] == (4321, 0)
    assert calls[-1] == (4321, DESKTOP_LOCK_SIGNAL)


def test_desktop_lock_fails_closed_without_live_supervisor(tmp_path):
    locker = SessionLocker(
        environ={"TETHER_BOOT_IMAGE": "1", "TETHER_DESKTOP": "1"},
        desktop_pid_file=str(tmp_path / "missing.pid"),
        desktop_request_file=str(tmp_path / "lock"),
    )

    result = locker.lock()

    assert result.available is False
    assert result.success is False
    assert not (tmp_path / "lock").exists()


def test_power_broker_only_writes_allowlisted_actions():
    with patch("app.privilege.os.open", return_value=17) as open_pipe, patch(
        "app.privilege.os.write"
    ) as write_pipe, patch("app.privilege.os.close") as close_pipe:
        result = PowerBrokerClient("/run/tether/control").request("reboot")

    assert result.success is True
    open_pipe.assert_called_once()
    write_pipe.assert_called_once_with(17, b"reboot\n")
    close_pipe.assert_called_once_with(17)


def test_power_broker_rejects_unknown_actions_without_opening_pipe():
    with patch("app.privilege.os.open") as open_pipe:
        result = PowerBrokerClient().request("shell")
    assert result.success is False
    open_pipe.assert_not_called()


class _FakeLocker:
    def __init__(self):
        self.calls = 0

    def available(self):
        return True

    def lock(self):
        self.calls += 1
        return SimpleNamespace(success=True, message="")


def test_shell_lock_command_delegates_to_trusted_locker():
    locker = _FakeLocker()
    shell = TetherShell(locker=locker)

    with patch("sys.stdout", new=io.StringIO()):
        shell._run_captured(["lock"])
        assert shell._lock_pending is True
        shell._perform_lock("manual")

    assert locker.calls == 1
    assert shell._lock_pending is False


def test_idle_lock_uses_configured_timeout():
    shell = TetherShell(locker=_FakeLocker())
    with patch("app.shell.time.monotonic", return_value=1000):
        assert shell._idle_lock_due(399) is True
        assert shell._idle_lock_due(401) is False
