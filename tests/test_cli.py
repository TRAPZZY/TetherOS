"""Tests for app.cli"""

import pytest
from unittest.mock import patch
from app.cli import CLI


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
