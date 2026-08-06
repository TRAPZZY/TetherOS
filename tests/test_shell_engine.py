import io
from unittest.mock import patch

from app.shell import TetherShell
from app.shell_parser import parse_line


def test_registry_contains_no_alias_cycles():
    shell = TetherShell()
    assert not {name: target for name, target in shell._aliases.items() if name == target}


def test_pipeline_passes_text_and_redirects_to_vfs():
    shell = TetherShell()
    with patch("sys.stdout", new=io.StringIO()):
        shell._execute('echo "hello world" | grep world > /tmp/result.txt', _from_script=True)
    assert "hello world" in shell._vfs.read("/tmp/result.txt")


def test_alias_expands_once_and_preserves_arguments():
    shell = TetherShell()
    output = shell._run_pipeline(parse_line("ll /etc").commands)
    assert "hostname" in output


def test_system_commands_do_not_use_command_shell():
    shell = TetherShell()
    completed = __import__("subprocess").CompletedProcess(["tool"], 0, "ok\n", "")
    with patch("app.shell.subprocess.run", return_value=completed) as run:
        output, _ = shell._run_captured(["tool", "argument"])
    assert output == "ok\n"
    assert run.call_args.kwargs["shell"] is False
