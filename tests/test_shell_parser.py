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


def test_parser_marks_final_ampersand_as_background_execution():
    parsed = parse_line("nmap 127.0.0.1 &")
    assert parsed.background is True
    assert parsed.commands[0].argv == ["nmap", "127.0.0.1"]


def test_parser_rejects_non_final_background_marker():
    with pytest.raises(ShellSyntaxError):
        parse_line("nmap & echo unsafe")
