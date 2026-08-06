from unittest.mock import patch

from app.gui import CommandDeckController, gui_available
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
