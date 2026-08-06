"""session.py -- Session logging for TRAP HUB"""

import os
import shlex
import time


_SENSITIVE_NAMES = {
    "login", "passwd", "password", "secret", "token", "api-key",
    "apikey", "cookie",
}
_SENSITIVE_FLAGS = {
    "--password", "--passwd", "--secret", "--token", "--api-key",
    "--cookie", "--cookie-jar",
}


def sanitize_command(command):
    """Return a history-safe command and whether its output must be omitted."""
    try:
        tokens = shlex.split(command, posix=True)
    except ValueError:
        lowered = command.lower()
        sensitive = any(word in lowered for word in _SENSITIVE_NAMES)
        return ("[sensitive command omitted]" if sensitive else command, sensitive)
    if not tokens:
        return "", False

    command_name = os.path.basename(tokens[0]).lower()
    if command_name in _SENSITIVE_NAMES:
        return shlex.join([tokens[0], "<redacted>"]), True
    sensitive = command_name in _SENSITIVE_NAMES or command_name == "hydra"
    redacted = []
    redact_next = False
    for token in tokens:
        lowered = token.lower()
        if redact_next:
            redacted.append("<redacted>")
            redact_next = False
            sensitive = True
            continue
        key = lowered.split("=", 1)[0]
        is_hydra_password = command_name == "hydra" and token == "-p"
        if key in _SENSITIVE_FLAGS or is_hydra_password:
            sensitive = True
            if "=" in token:
                redacted.append(token.split("=", 1)[0] + "=<redacted>")
            else:
                redacted.append(token)
                redact_next = True
            continue
        redacted.append(token)
    return shlex.join(redacted), sensitive


def _log_path():
    d = os.path.join(os.path.expanduser("~"), ".tether")
    os.makedirs(d, mode=0o700, exist_ok=True)
    try:
        os.chmod(d, 0o700)
    except OSError:
        pass
    return os.path.join(d, "session.log")


def _open_private_log(path):
    flags = os.O_WRONLY | os.O_APPEND | os.O_CREAT
    flags |= getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o600)
    try:
        os.chmod(path, 0o600)
        return os.fdopen(descriptor, "a", encoding="utf-8")
    except Exception:
        os.close(descriptor)
        raise


def log_cmd(cmd, output=""):
    path = _log_path()
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    safe_cmd, sensitive = sanitize_command(cmd)
    safe_output = "[sensitive output omitted]" if sensitive and output else output
    try:
        with _open_private_log(path) as f:
            f.write(f"[{ts}] $ {safe_cmd}\n")
            if safe_output:
                for line in safe_output.strip().split("\n"):
                    f.write(f"[{ts}]   {line}\n")
            f.write("\n")
    except (OSError, UnicodeError):
        pass


def view_log(n=50):
    path = _log_path()
    if not os.path.isfile(path):
        return ["(no session log yet)"]
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        return lines[-n:]
    except (OSError, UnicodeError):
        return ["(error reading log)"]
