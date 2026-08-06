"""network.py -- Network utilities for Tether OS
Cross-platform helpers: Tor detection, proxy env, OS info.
"""

import platform
import socket
import subprocess
import os
import shutil
import http.client
import ssl
import urllib.request

try:
    import socks
except ImportError:  # surfaced as a clear runtime error by Tor helpers
    socks = None

SYSTEM = platform.system().lower()


class TorDependencyError(RuntimeError):
    pass


def _require_socks():
    if socks is None:
        raise TorDependencyError("PySocks is required for Tor networking")


def create_connection(host, port, timeout=10, use_tor=True,
                      proxy_host="127.0.0.1", proxy_port=9050):
    """Create a TCP connection, resolving hostnames through Tor by default."""
    if not use_tor:
        return socket.create_connection((host, port), timeout=timeout)
    _require_socks()
    sock = socks.socksocket()
    sock.set_proxy(socks.SOCKS5, proxy_host, proxy_port, rdns=True)
    sock.settimeout(timeout)
    try:
        sock.connect((host, port))
        return sock
    except Exception:
        sock.close()
        raise


class _SocksHTTPConnection(http.client.HTTPConnection):
    def __init__(self, host, proxy_host, proxy_port, **kwargs):
        self._proxy_host = proxy_host
        self._proxy_port = proxy_port
        super().__init__(host, **kwargs)

    def connect(self):
        self.sock = create_connection(
            self.host,
            self.port,
            timeout=self.timeout,
            use_tor=True,
            proxy_host=self._proxy_host,
            proxy_port=self._proxy_port,
        )
        if self._tunnel_host:
            self._tunnel()


class _SocksHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, host, proxy_host, proxy_port, **kwargs):
        self._proxy_host = proxy_host
        self._proxy_port = proxy_port
        super().__init__(host, **kwargs)

    def connect(self):
        self.sock = create_connection(
            self.host,
            self.port,
            timeout=self.timeout,
            use_tor=True,
            proxy_host=self._proxy_host,
            proxy_port=self._proxy_port,
        )
        server_hostname = self.host
        if self._tunnel_host:
            self._tunnel()
            server_hostname = self._tunnel_host
        self.sock = self._context.wrap_socket(self.sock, server_hostname=server_hostname)


class _SocksHTTPHandler(urllib.request.HTTPHandler):
    def __init__(self, proxy_host, proxy_port):
        super().__init__()
        self.proxy_host = proxy_host
        self.proxy_port = proxy_port

    def http_open(self, req):
        def connection(host, timeout=socket._GLOBAL_DEFAULT_TIMEOUT, **kwargs):
            return _SocksHTTPConnection(
                host,
                proxy_host=self.proxy_host,
                proxy_port=self.proxy_port,
                timeout=timeout,
                **kwargs,
            )
        return self.do_open(connection, req)


class _SocksHTTPSHandler(urllib.request.HTTPSHandler):
    def __init__(self, proxy_host, proxy_port, context=None):
        super().__init__(context=context)
        self.proxy_host = proxy_host
        self.proxy_port = proxy_port

    def https_open(self, req):
        def connection(host, timeout=socket._GLOBAL_DEFAULT_TIMEOUT, **kwargs):
            return _SocksHTTPSConnection(
                host,
                proxy_host=self.proxy_host,
                proxy_port=self.proxy_port,
                timeout=timeout,
                **kwargs,
            )
        return self.do_open(
            connection,
            req,
            context=self._context,
            check_hostname=self._check_hostname,
        )


def build_tor_opener(proxy_host="127.0.0.1", proxy_port=9050, context=None):
    _require_socks()
    return urllib.request.build_opener(
        _SocksHTTPHandler(proxy_host, proxy_port),
        _SocksHTTPSHandler(proxy_host, proxy_port, context=context),
    )


def open_url(request, timeout=10, use_tor=True, proxy_host="127.0.0.1",
             proxy_port=9050, context=None):
    if not use_tor:
        return urllib.request.urlopen(request, timeout=timeout, context=context)
    return build_tor_opener(proxy_host, proxy_port, context=context).open(
        request, timeout=timeout
    )


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
    for key in [
        "HTTP_PROXY", "HTTPS_PROXY", "SOCKS_PROXY", "ALL_PROXY", "NO_PROXY",
        "http_proxy", "https_proxy", "socks_proxy", "all_proxy", "no_proxy",
    ]:
        os.environ.pop(key, None)


def get_os():
    return {
        "system": SYSTEM,
        "release": platform.release(),
        "machine": platform.machine(),
    }
