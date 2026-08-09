import os
import stat
from unittest.mock import patch

from app.gui import (
    CommandDeckController,
    clear_ready_marker,
    gui_available,
    publish_ready_marker,
)
from app.shell import TetherShell


def test_gui_dependency_probe_does_not_import_gtk():
    with patch("app.gui.importlib.util.find_spec", return_value=None):
        assert gui_available() is False


def test_gui_controller_uses_shared_shell_contracts():
    controller = CommandDeckController(TetherShell())

    response = controller.execute("echo graphical-shell")
    state = controller.state()

    assert response.exit_code == 0
    assert "graphical-shell" in response.stdout
    assert response.command_id
    assert state.command_count > 50


def test_gui_controller_reports_parser_errors_without_crashing():
    controller = CommandDeckController(TetherShell())
    response = controller.execute("echo 'unterminated")
    assert response.exit_code == 2
    assert "syntax error" in response.stdout


def test_entrypoint_routes_gui_mode_without_loading_interactive_shell():
    with patch("app.gui.main", return_value=19) as gui_main:
        from app.entrypoint import main

        assert main(["--gui", "--windowed"]) == 19
    gui_main.assert_called_once_with(["--windowed"])


def test_gui_ready_marker_has_an_explicit_lifecycle(tmp_path):
    marker = tmp_path / "gui.ready"
    marker.write_text("stale")
    marker.chmod(0o666)
    publish_ready_marker(str(marker))
    assert marker.read_text() == "TRAP_HUB_GUI_READY\n"
    if os.name == "posix":
        assert stat.S_IMODE(marker.stat().st_mode) == 0o600
    clear_ready_marker(str(marker))
    assert not marker.exists()


def test_gui_ready_marker_refuses_symlinks_on_supported_hosts(tmp_path):
    if not getattr(os, "O_NOFOLLOW", 0):
        return
    target = tmp_path / "target"
    target.write_text("do not overwrite")
    marker = tmp_path / "gui.ready"
    marker.symlink_to(target)
    try:
        publish_ready_marker(str(marker))
    except OSError:
        pass
    else:
        raise AssertionError("GUI readiness marker followed a symbolic link")
    assert target.read_text() == "do not overwrite"
