"""Boot a TetherOS ISO and verify authentication and edition contracts."""

import argparse
from pathlib import Path
import re
import shutil
import socket
import sys
import tempfile
import time


SESSION_PASSWORD = "TRAP-HUB-Test-Session-2026!"
INVALID_PASSWORD = "Wrong-Password-2026!"
SHELL_PROMPT_PATTERN = r"\x1b\[[0-9;]*m>\x1b\[[0-9;]*m "
SCHEDULER_READY_PATTERN = r"Scheduler started -- rotating IP every \d+s"


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


def _connect_monitor(path, timeout=10):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        monitor = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            monitor.connect(str(path))
            monitor.settimeout(1)
            try:
                monitor.recv(4096)
            except TimeoutError:
                pass
            return monitor
        except OSError:
            monitor.close()
            time.sleep(0.1)
    raise RuntimeError("QEMU monitor did not become available")


def _key_name(character):
    if "a" <= character <= "z" or "0" <= character <= "9":
        return character
    if "A" <= character <= "Z":
        return f"shift-{character.lower()}"
    names = {
        "-": "minus",
        "_": "shift-minus",
        "!": "shift-1",
        "@": "shift-2",
        ".": "dot",
    }
    try:
        return names[character]
    except KeyError as exc:
        raise ValueError(f"unsupported QEMU test key: {character!r}") from exc


def _send_monitor_text(monitor_path, text):
    with _connect_monitor(monitor_path) as monitor:
        for character in text:
            command = f"sendkey {_key_name(character)} 20\n"
            monitor.sendall(command.encode("ascii"))
            time.sleep(0.04)
        monitor.sendall(b"sendkey ret 20\n")


def _send_serial_line(child, text, delay=0.01):
    """Pace UART input so QEMU cannot overrun and truncate a command."""
    for character in text:
        child.send(character)
        time.sleep(delay)
    child.send("\n")


def _console_line_pattern(text):
    """Match a rendered console value across terminal newline translation."""
    return rf"{re.escape(text)}\r*\n"


def _guest_path_pattern(label):
    """Match a marker probe while retaining its PRESENT/ABSENT state."""
    return rf"{re.escape(label)}_(PRESENT|ABSENT)\r*\n"


def _wait_for_guest_path(child, path, *, label, exists=True, attempts=45):
    expected = "PRESENT" if exists else "ABSENT"
    for _attempt in range(attempts):
        code = (
            "import os; print(" + repr(label) + " + "
            f"('_PRESENT' if os.path.exists({path!r}) else '_ABSENT'))"
        )
        _send_serial_line(child, f'python3 -c "{code}"')
        child.expect(_guest_path_pattern(label), timeout=10)
        if child.match.group(1) == expected:
            return
        time.sleep(1)
    state = "appear" if exists else "disappear"
    raise RuntimeError(f"guest path did not {state}: {path}")


def _validate_framebuffer(screenshot):
    image = screenshot.read_bytes()
    if not image.startswith(b"P6") or len(image) < 4096:
        raise RuntimeError("QEMU desktop screenshot is missing or invalid")
    try:
        magic, dimensions, maximum, pixels = image.split(b"\n", 3)
        width, height = (int(value) for value in dimensions.split())
    except (TypeError, ValueError) as exc:
        raise RuntimeError("QEMU desktop screenshot has an invalid PPM header") from exc
    if magic != b"P6" or maximum != b"255" or width <= 0 or height <= 0:
        raise RuntimeError("QEMU desktop screenshot has an invalid PPM header")
    required_bytes = width * height * 3
    if len(pixels) < required_bytes:
        raise RuntimeError("QEMU desktop screenshot has truncated pixel data")
    sample = pixels[:min(required_bytes, 200_000)]
    if len(set(sample)) < 8:
        raise RuntimeError("QEMU desktop screenshot appears blank")


def _capture_framebuffer(monitor_path, screenshot_path):
    screenshot = Path(screenshot_path).resolve()
    screenshot.parent.mkdir(parents=True, exist_ok=True)
    if any(character in str(screenshot) for character in ('"', "\n", "\r")):
        raise ValueError("unsafe screenshot path")
    with _connect_monitor(monitor_path) as monitor:
        monitor.sendall(f'screendump "{screenshot}"\n'.encode("utf-8"))
    deadline = time.monotonic() + 10
    last_size = -1
    stable_reads = 0
    while time.monotonic() < deadline:
        size = screenshot.stat().st_size if screenshot.is_file() else -1
        stable_reads = stable_reads + 1 if size > 4096 and size == last_size else 0
        if stable_reads >= 2:
            break
        last_size = size
        time.sleep(0.1)
    if stable_reads < 2:
        raise RuntimeError("QEMU did not create the desktop screenshot")
    _validate_framebuffer(screenshot)


def _enforce_boot_budget(started, budget, *, now=None):
    elapsed = (time.monotonic() if now is None else now) - started
    if elapsed > budget:
        raise RuntimeError(
            f"boot-to-shell took {elapsed:.1f}s; budget is {budget:.1f}s"
        )
    return elapsed


def run_smoke(
    iso_path,
    *,
    edition="core",
    timeout=300,
    boot_budget=180,
    screenshot_path=None,
):
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

    monitor_dir = tempfile.TemporaryDirectory(prefix="tether-qemu-")
    monitor_path = Path(monitor_dir.name) / "monitor.sock"

    started = time.monotonic()
    child = pexpect.spawn(
        qemu,
        [
            "-accel", "tcg",
            "-m", "1024" if edition == "desktop" else "512",
            "-cdrom", str(iso),
            "-display", "none",
            "-device", "virtio-vga" if edition == "desktop" else "VGA",
            "-serial", "stdio",
            "-monitor", f"unix:{monitor_path},server=on,wait=off",
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
        _send_serial_line(child, "")
        child.expect("(?i)new password")
        _send_serial_line(child, SESSION_PASSWORD)
        child.expect("(?i)retype password")
        _send_serial_line(child, SESSION_PASSWORD)
        child.expect("TRAP HUB session password configured")
        child.expect("(?i)password:")
        _send_serial_line(child, INVALID_PASSWORD)
        child.expect("(?i)login incorrect")
        child.expect("(?i)password:")
        _send_serial_line(child, SESSION_PASSWORD)
        child.expect("SECURE TERMINAL")
        child.expect(SCHEDULER_READY_PATTERN)
        child.expect(SHELL_PROMPT_PATTERN)
        boot_elapsed = _enforce_boot_budget(started, boot_budget)
        print(f"TRAP HUB boot-to-shell: {boot_elapsed:.1f}s")

        _send_serial_line(child, "deck --json")
        child.expect('"command_count"')
        child.expect('"lock_ready": true')

        _send_serial_line(child, "cat /etc/tether-edition")
        child.expect(_console_line_pattern(edition))

        if edition == "desktop":
            _send_serial_line(child, "which weston")
            child.expect("/usr/bin/weston")
            _send_serial_line(
                child,
                'python3 -c "import gi; gi.require_version(\'Gtk\', \'3.0\'); '
                'from gi.repository import Gtk; print(\'GTK_READY\')"'
            )
            child.expect("GTK_READY")
            _send_serial_line(child, "ls /dev/dri/card0")
            child.expect("/dev/dri/card0")

            _wait_for_guest_path(
                child,
                "/run/user/1000/trap-hub-local-login.ready",
                label="LOCAL_LOGIN",
            )
            _send_monitor_text(monitor_path, SESSION_PASSWORD)
            _wait_for_guest_path(
                child,
                "/run/user/1000/trap-hub-gui.ready",
                label="GUI",
            )

            # Exercise the real desktop lock path: signal the trusted session
            # supervisor, prove the realized GUI disappears, unlock vlock on
            # tty1, and prove Weston/GTK return.
            _send_serial_line(
                child,
                'python3 -c "import os,signal; '
                "os.kill(int(open('/run/user/1000/trap-hub-desktop.pid').read()), "
                'signal.SIGUSR1)"'
            )
            _wait_for_guest_path(
                child,
                "/run/user/1000/trap-hub-gui.ready",
                label="GUI",
                exists=False,
            )
            _wait_for_guest_path(
                child,
                "/run/user/1000/trap-hub-lock.active",
                label="DESKTOP_LOCK",
            )
            _send_monitor_text(monitor_path, INVALID_PASSWORD)
            time.sleep(2)
            _wait_for_guest_path(
                child,
                "/run/user/1000/trap-hub-lock.active",
                label="DESKTOP_LOCK",
                attempts=1,
            )
            _send_monitor_text(monitor_path, SESSION_PASSWORD)
            _wait_for_guest_path(
                child,
                "/run/user/1000/trap-hub-gui.ready",
                label="GUI",
            )
            _wait_for_guest_path(
                child,
                "/run/user/1000/trap-hub-lock.active",
                label="DESKTOP_LOCK",
                exists=False,
            )
            if screenshot_path:
                _capture_framebuffer(monitor_path, screenshot_path)

        _send_serial_line(child, "which vlock")
        child.expect("/usr/bin/vlock")

        # Serial consoles cannot use VT_LOCKSWITCH. TRAP HUB locks them by
        # ending the session, after which getty/login must re-authenticate.
        _send_serial_line(child, "lock")
        child.expect("(?i)password:")
        _send_serial_line(child, INVALID_PASSWORD)
        child.expect("(?i)login incorrect")
        child.expect("(?i)password:")
        _send_serial_line(child, SESSION_PASSWORD)
        child.expect("SECURE TERMINAL")
        child.expect(SCHEDULER_READY_PATTERN)
        child.expect(SHELL_PROMPT_PATTERN)

        _send_serial_line(child, "exit")
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
        monitor_dir.cleanup()


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("iso")
    parser.add_argument("--edition", choices=("core", "desktop"), default="core")
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--boot-budget", type=float, default=180)
    parser.add_argument("--screenshot")
    args = parser.parse_args(argv)
    return run_smoke(
        args.iso,
        edition=args.edition,
        timeout=args.timeout,
        boot_budget=args.boot_budget,
        screenshot_path=args.screenshot,
    )


if __name__ == "__main__":
    raise SystemExit(main())
