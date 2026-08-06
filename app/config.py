"""Typed runtime configuration for Tether OS.

Configuration is intentionally small and dependency-free so the same loader can
run in the Buildroot image and in desktop installations.
"""

from dataclasses import dataclass
import configparser
import os
import sys
from pathlib import Path
from typing import Iterable, Optional


@dataclass(frozen=True)
class TetherConfig:
    rotation_interval: int = 60
    auto_rotate: bool = True
    tor_host: str = "127.0.0.1"
    tor_socks_port: int = 9050
    tor_control_port: int = 9051
    tor_password: Optional[str] = None
    tor_cookie_path: Optional[str] = None
    lock_enabled: bool = True
    lock_timeout_seconds: int = 600

    def tor_options(self):
        return {
            "tor_host": self.tor_host,
            "tor_socks_port": self.tor_socks_port,
            "tor_control_port": self.tor_control_port,
            "tor_password": self.tor_password,
            "tor_cookie_path": self.tor_cookie_path,
        }


def _candidate_paths() -> Iterable[Path]:
    configured = os.environ.get("TETHER_CONFIG")
    if configured:
        yield Path(configured).expanduser()

    yield Path("/etc/tether.conf")
    yield Path(__file__).resolve().parent.parent / "etc" / "tether.conf"
    yield Path(sys.prefix) / "share" / "tether-os" / "etc" / "tether.conf"
    yield Path.home() / ".tether" / "tether.conf"


def _clean(value: str) -> str:
    value = value.split("#", 1)[0].strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        value = value[1:-1]
    return value


def _get_int(parser, section, option, default, minimum=1, maximum=65535):
    try:
        value = int(_clean(parser.get(section, option)))
    except (configparser.Error, TypeError, ValueError):
        return default
    return value if minimum <= value <= maximum else default


def _get_bool(parser, section, option, default):
    try:
        value = _clean(parser.get(section, option)).lower()
    except (configparser.Error, TypeError):
        return default
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    return default


def load_config(path=None):
    parser = configparser.ConfigParser(inline_comment_prefixes=("#", ";"))
    selected = Path(path).expanduser() if path else next(
        (candidate for candidate in _candidate_paths() if candidate.is_file()),
        None,
    )
    if selected:
        try:
            parser.read(str(selected), encoding="utf-8")
        except (OSError, configparser.Error):
            parser = configparser.ConfigParser()

    password = None
    cookie_path = None
    try:
        password = _clean(parser.get("tor", "password")) or None
    except (configparser.Error, TypeError):
        pass
    try:
        cookie_path = _clean(parser.get("tor", "cookie_path")) or None
    except (configparser.Error, TypeError):
        pass

    host = "127.0.0.1"
    try:
        host = _clean(parser.get("tor", "host")) or host
    except (configparser.Error, TypeError):
        pass

    return TetherConfig(
        rotation_interval=_get_int(parser, "tether", "rotation_interval", 60, 10, 86400),
        auto_rotate=_get_bool(parser, "tether", "auto_rotate", True),
        tor_host=host,
        tor_socks_port=_get_int(parser, "tor", "socks_port", 9050),
        tor_control_port=_get_int(parser, "tor", "control_port", 9051),
        tor_password=password,
        tor_cookie_path=cookie_path,
        lock_enabled=_get_bool(parser, "security", "lock_enabled", True),
        lock_timeout_seconds=_get_int(
            parser, "security", "lock_timeout_seconds", 600, 30, 86400
        ),
    )
