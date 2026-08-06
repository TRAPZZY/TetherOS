"""Tests for app.cli"""

import pytest
from unittest.mock import patch
from app.cli import CLI
from app.entrypoint import main as entrypoint_main


class TestCLI:
    def test_init(self):
        cli = CLI()
        assert cli.parser.prog == "tether"

    def test_run_no_args_shows_help(self):
        cli = CLI()
        rc = cli.run([])
        assert rc == 0

    def test_info(self):
        cli = CLI()
        rc = cli.run(["info"])
        assert rc == 0

    def test_check(self):
        cli = CLI()
        rc = cli.run(["check"])
        assert rc == 0

    def test_version(self):
        cli = CLI()
        with pytest.raises(SystemExit):
            cli.run(["--version"])


def test_entrypoint_routes_cli_commands():
    with patch("app.cli.CLI.run", return_value=7) as run:
        assert entrypoint_main(["status"]) == 7
    run.assert_called_once_with(["status"])


def test_entrypoint_routes_interactive_mode():
    with patch("app.shell.main", return_value=0) as shell_main:
        assert entrypoint_main([]) == 0
    shell_main.assert_called_once_with()
