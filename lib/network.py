"""network.py -- Network utilities for Tether OS
Cross-platform helpers: Tor detection, proxy env, OS info.
"""

import platform
import socket
import subprocess
import os
import shutil

SYSTEM = platform.system().lower()


def _find_tor():
    candidates = ["tor", "tor.exe"]
    for cmd in candidates:
        path = shutil.which(cmd)
        if path:
            return path
    search_paths = []
    if SYSTEM == "windows":
        search_paths = [
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "Tor", "tor.exe"),
            os.path.join(os.environ.get("PROGRAMFILES", "C:\\Program Files"), "Tor", "tor.exe"),
            os.path.join(os.environ.get("USERPROFILE", ""), "Desktop", "Tor Browser",
                         "Browser", "TorBrowser", "Tor", "tor.exe"),
            os.path.join(os.environ.get("USERPROFILE", ""), "Downloads", "Tor Browser",
                         "Browser", "TorBrowser", "Tor", "tor.exe"),
            os.path.join(os.environ.get("USERPROFILE", ""), ".tether", "tor", "tor.exe"),
        ]
    elif SYSTEM == "darwin":
        search_paths = [
            "/Applications/Tor Browser.app/Contents/Resources/TorBrowser/Tor/tor",
            os.path.expanduser("~/Applications/Tor Browser.app/Contents/Resources/TorBrowser/Tor/tor"),
            os.path.expanduser("~/.tether/tor/tor"),
        ]
    for p in search_paths:
        if os.path.isfile(p):
            return p
    return None


def check_tor():
    path = _find_tor()
    if not path:
        return False
    try:
        r = subprocess.run(
            [path, "--version"],
            capture_output=True, text=True, timeout=5,
        )
        return r.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False


def check_tor_service():
    if SYSTEM == "linux":
        for cmd in [
            ["systemctl", "is-active", "tor"],
            ["service", "tor", "status"],
        ]:
            try:
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                if r.returncode == 0:
                    return True
            except (FileNotFoundError, subprocess.TimeoutExpired):
                continue
        return False
    elif SYSTEM == "darwin":
        try:
            r = subprocess.run(
                ["brew", "services", "list", "tor"],
                capture_output=True, text=True, timeout=5,
            )
            return "started" in r.stdout
        except (FileNotFoundError, subprocess.TimeoutExpired):
            try:
                r = subprocess.run(
                    ["pgrep", "-x", "tor"],
                    capture_output=True, text=True, timeout=5,
                )
                return r.returncode == 0
            except (FileNotFoundError, subprocess.TimeoutExpired):
                return False
    elif SYSTEM == "windows":
        try:
            r = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq tor.exe"],
                capture_output=True, text=True, timeout=5,
            )
            return "tor.exe" in r.stdout
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False
    return False


def check_port(host, port, timeout=3):
    s = socket.socket()
    try:
        s.settimeout(timeout)
        s.connect((host, port))
        s.close()
        return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False
    finally:
        s.close()


def detect_tor_browser():
    """Detect if Tor Browser is installed and its SOCKS port."""
    if check_port("127.0.0.1", 9150):
        return {"detected": True, "socks_port": 9150, "type": "browser"}
    return {"detected": False}


def detect_system_tor():
    """Detect if system Tor daemon is running with full control port access."""
    socks = check_port("127.0.0.1", 9050)
    control = check_port("127.0.0.1", 9051)
    if socks and control:
        return {"detected": True, "type": "full", "socks_port": 9050, "control_port": 9051}
    if socks:
        return {"detected": True, "type": "partial", "socks_port": 9050, "control_port": None}
    return {"detected": False}


def set_proxy(http_proxy="127.0.0.1:8118", socks_proxy="127.0.0.1:9050"):
    os.environ["HTTP_PROXY"] = f"http://{http_proxy}"
    os.environ["HTTPS_PROXY"] = f"http://{http_proxy}"
    os.environ["SOCKS_PROXY"] = f"socks5://{socks_proxy}"
    os.environ["ALL_PROXY"] = f"socks5://{socks_proxy}"
    os.environ["NO_PROXY"] = "localhost,127.0.0.1"


def unset_proxy():
    for key in ["HTTP_PROXY", "HTTPS_PROXY", "SOCKS_PROXY", "ALL_PROXY", "NO_PROXY"]:
        os.environ.pop(key, None)


def get_os():
    return {
        "system": SYSTEM,
        "release": platform.release(),
        "machine": platform.machine(),
    }
