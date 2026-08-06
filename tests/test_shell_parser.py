import pytest

from app.shell_parser import ShellSyntaxError, parse_line


def test_quotes_pipeline_and_redirect():
    parsed = parse_line('echo "hello world" | grep world >> /tmp/result.txt')
    assert [command.argv for command in parsed.commands] == [
        ["echo", "hello world"],
        ["grep", "world"],
    ]
    assert parsed.redirect_path == "/tmp/result.txt"
    assert parsed.append is True


@pytest.mark.parametrize("line", ["| echo bad", "echo bad |", "echo bad >", "echo > a > b"])
def test_rejects_invalid_syntax(line):
    with pytest.raises(ShellSyntaxError):
        parse_line(line)
