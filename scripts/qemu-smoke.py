"""Boot a TetherOS ISO and verify authentication and edition contracts."""

import argparse
from pathlib import Path
import shutil
import sys


SESSION_PASSWORD = "TRAP-HUB-Test-Session-2026!"


class RedactingTranscript:
    """Keep enough serial output to diagnose a smoke failure without secrets."""

    def __init__(self, secret, limit=12_000):
        self._secret = secret
        self._limit = limit
        self._text = ""

    def write(self, value):
        self._text = (self._text + value.replace(self._secret, "[REDACTED]"))[-self._limit :]

    def flush(self):
        pass

    def tail(self):
        return self._text or "[no serial output captured]"


def run_smoke(iso_path, *, edition="core", timeout=300):
    try:
        import pexpect
    except ImportError as exc:
        raise RuntimeError("qemu-smoke requires the pexpect package") from exc

    qemu = shutil.which("qemu-system-x86_64")
    if not qemu:
        raise RuntimeError("qemu-system-x86_64 is not installed")
    iso = Path(iso_path).resolve()
    if not iso.is_file():
        raise FileNotFoundError(iso)

    child = pexpect.spawn(
        qemu,
        [
            "-accel", "tcg",
            "-m", "1024" if edition == "desktop" else "512",
            "-cdrom", str(iso),
            "-display", "none",
            "-device", "virtio-vga" if edition == "desktop" else "VGA",
            "-serial", "stdio",
            "-no-reboot",
        ],
        encoding="utf-8",
        codec_errors="replace",
        timeout=timeout,
    )
    transcript = RedactingTranscript(SESSION_PASSWORD)
    child.logfile_read = transcript
    try:
        child.expect("TRAP HUB // SECURE SESSION SETUP")
        child.sendline("")
        child.expect("(?i)new password")
        child.sendline(SESSION_PASSWORD)
        child.expect("(?i)retype password")
        child.sendline(SESSION_PASSWORD)
        child.expect("TRAP HUB session password configured")
        child.expect("(?i)password:")
        child.sendline(SESSION_PASSWORD)
        child.expect("SECURE TERMINAL")

        child.sendline("deck --json")
        child.expect('"command_count"')
        child.expect('"lock_ready": true')

        child.sendline("cat /etc/tether-edition")
        child.expect(rf"\r?\n{edition}\r?\n")

        if edition == "desktop":
            child.sendline("which weston")
            child.expect("/usr/bin/weston")
            child.sendline(
                'python3 -c "import gi; gi.require_version(\'Gtk\', \'3.0\'); '
                'from gi.repository import Gtk; print(\'GTK_READY\')"'
            )
            child.expect("GTK_READY")
            child.sendline("ls /dev/dri/card0")
            child.expect("/dev/dri/card0")

        child.sendline("which vlock")
        child.expect("/usr/bin/vlock")

        # Serial consoles cannot use VT_LOCKSWITCH. TRAP HUB locks them by
        # ending the session, after which getty/login must re-authenticate.
        child.sendline("lock")
        child.expect("(?i)password:")
        child.sendline(SESSION_PASSWORD)
        child.expect("SECURE TERMINAL")

        child.sendline("exit")
        child.expect("(?i)password:")
        return 0
    except Exception as exc:
        raise RuntimeError(
            "TetherOS QEMU smoke failed; redacted serial transcript follows:\n"
            f"{transcript.tail()}"
        ) from exc
    finally:
        sys.stdout.write(transcript.tail())
        sys.stdout.flush()
        child.close(force=True)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("iso")
    parser.add_argument("--edition", choices=("core", "desktop"), default="core")
    parser.add_argument("--timeout", type=int, default=300)
    args = parser.parse_args(argv)
    return run_smoke(args.iso, edition=args.edition, timeout=args.timeout)


if __name__ == "__main__":
    raise SystemExit(main())
