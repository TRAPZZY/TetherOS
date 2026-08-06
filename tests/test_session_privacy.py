from unittest.mock import patch

from app.session import log_cmd, sanitize_command


def test_hydra_password_is_redacted_and_marks_output_sensitive():
    command, sensitive = sanitize_command(
        "hydra -l admin -p super-secret ssh://192.0.2.1"
    )

    assert sensitive is True
    assert "super-secret" not in command
    assert "<redacted>" in command


def test_generic_inline_token_is_redacted():
    command, sensitive = sanitize_command("tool --token=abc123 status")

    assert sensitive is True
    assert "abc123" not in command
    assert "--token=<redacted>" in command


def test_sensitive_command_never_records_positional_arguments():
    command, sensitive = sanitize_command("password never-write-this")

    assert sensitive is True
    assert "never-write-this" not in command
    assert "<redacted>" in command


def test_sensitive_command_output_is_never_written_to_session_log(tmp_path):
    path = tmp_path / "session.log"
    with patch("app.session._log_path", return_value=str(path)):
        log_cmd("hydra -l admin -p secret ssh://host", "Valid: admin:secret")

    content = path.read_text(encoding="utf-8")
    assert "admin:secret" not in content
    assert "-p secret" not in content
    assert "sensitive output omitted" in content


def test_safe_commands_remain_readable_in_history():
    command, sensitive = sanitize_command('echo "hello world"')
    assert sensitive is False
    assert command == "echo 'hello world'"
