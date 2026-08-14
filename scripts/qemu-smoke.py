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


def _require_guest_capability(child, code, *, label):
    """Run a probe whose marker cannot be satisfied by terminal echo."""
    if f"{label}_PRESENT" in code or f"{label}_ABSENT" in code:
        raise ValueError("guest probe embeds its own rendered result marker")
    _send_serial_line(child, f'python3 -c "{code}"')
    child.expect(_guest_path_pattern(label), timeout=10)
    state = child.match.group(1)
    if state != "PRESENT":
        raise RuntimeError(f"guest capability is unavailable: {label}")


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


def _qemu_boot_args(
    iso,
    *,
    edition,
    monitor_path,
    firmware="bios",
    media="optical",
    uefi_code=None,
    uefi_vars=None,
):
    if firmware not in {"bios", "uefi"}:
        raise ValueError(f"unsupported firmware: {firmware}")
    if media not in {"optical", "usb"}:
        raise ValueError(f"unsupported boot media: {media}")
    args = [
        "-accel", "tcg",
        "-machine", "q35" if firmware == "uefi" else "pc",
        "-m", "1024" if edition == "desktop" else "512",
    ]
    if firmware == "uefi":
        code = Path(uefi_code).resolve() if uefi_code else None
        variables = Path(uefi_vars).resolve() if uefi_vars else None
        if not code or not code.is_file():
            raise FileNotFoundError("OVMF code firmware is unavailable")
        if not variables or not variables.is_file():
            raise FileNotFoundError("writable OVMF variables file is unavailable")
        args.extend([
            "-drive", f"if=pflash,format=raw,unit=0,readonly=on,file={code}",
            "-drive", f"if=pflash,format=raw,unit=1,file={variables}",
        ])
    if media == "optical":
        args.extend(["-cdrom", str(iso)])
    else:
        args.extend([
            "-drive", f"if=none,id=stick,format=raw,readonly=on,file={iso}",
            "-device", "qemu-xhci,id=xhci",
            "-device", "usb-storage,bus=xhci.0,drive=stick,bootindex=1",
        ])
    args.extend([
        "-display", "none",
        "-device", "virtio-vga" if edition == "desktop" else "VGA",
        "-serial", "stdio",
        "-monitor", f"unix:{monitor_path},server=on,wait=off",
        "-no-reboot",
    ])
    return args


def run_smoke(
    iso_path,
    *,
    edition="core",
    timeout=300,
    boot_budget=180,
    screenshot_path=None,
    firmware="bios",
    media="optical",
    uefi_code=None,
    uefi_vars=None,
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
    writable_uefi_vars = None
    if firmware == "uefi":
        source_vars = Path(uefi_vars).resolve() if uefi_vars else None
        if not source_vars or not source_vars.is_file():
            monitor_dir.cleanup()
            raise FileNotFoundError("OVMF variables template is unavailable")
        writable_uefi_vars = Path(monitor_dir.name) / "OVMF_VARS.fd"
        shutil.copyfile(source_vars, writable_uefi_vars)

    started = time.monotonic()
    child = pexpect.spawn(
        qemu,
        _qemu_boot_args(
            iso,
            edition=edition,
            monitor_path=monitor_path,
            firmware=firmware,
            media=media,
            uefi_code=uefi_code,
            uefi_vars=writable_uefi_vars,
        ),
        encoding="utf-8",
        codec_errors="replace",
        timeout=timeout,
    )
    transcript = RedactingTranscript(SESSION_PASSWORD)
    child.logfile_read = transcript
    try:
        child.expect("Tether OS ready.")
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

        _send_serial_line(child, "id -u tor")
        child.expect(r"([1-9][0-9]*)\r*\n")
        _send_serial_line(child, "pidof tor")
        child.expect(r"[1-9][0-9]*(?: [1-9][0-9]*)*\r*\n")
        _send_serial_line(child, "netstat -lnt")
        child.expect(r"127\.0\.0\.1:9050")

        _send_serial_line(child, "cat /etc/tether-edition")
        child.expect(_console_line_pattern(edition))

        if edition == "desktop":
            _send_serial_line(child, "which weston")
            child.expect("/usr/bin/weston")
            _require_guest_capability(
                child,
                "from gi.repository import GIRepository; "
                "versions=GIRepository.Repository.get_default().enumerate_versions('Gtk'); "
                "print('GTK_' + ('PRESENT' if '3.0' in versions else 'ABSENT'))",
                label="GTK",
            )
            _require_guest_capability(
                child,
                "import os,stat; path='/dev/dri/card0'; "
                "mode=os.stat(path).st_mode if os.path.exists(path) else 0; "
                "print('DRM_' + ('PRESENT' if stat.S_ISCHR(mode) else 'ABSENT'))",
                label="DRM",
            )

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

            # Create state and a live managed job in the long-lived GUI
            # backend. The presentation process is about to be destroyed by
            # lock; both must still exist after a new GTK client reconnects.
            _require_guest_capability(
                child,
                "import sys; sys.path.insert(0,'/usr/lib/tether-os'); "
                "from app.gui_backend import ShellRpcClient as C; "
                "c=C('/run/user/1000/trap-hub-shell.sock'); "
                "a=c.request('execute',{'line':'mkdir continuity'}); "
                "b=c.request('execute',{'line':'cd continuity'}); "
                "j=c.request('execute',{'line':'/bin/sleep 120 &'}); "
                "ok=all(x.get('exit_code') == 0 for x in (a,b,j)); "
                "print('BACKEND_SETUP_' + ('PRESENT' if ok else 'ABSENT'))",
                label="BACKEND_SETUP",
            )

            # Exercise the real desktop lock path: signal the trusted session
            # supervisor, prove the realized GUI disappears, unlock vlock on
            # tty1, and prove Weston/GTK return.
            _require_guest_capability(
                child,
                "import sys; sys.path.insert(0,'/usr/lib/tether-os'); "
                "from app.gui_backend import ShellRpcClient as C; "
                "r=C('/run/user/1000/trap-hub-shell.sock').request('lock'); "
                "ok=r.get('success') and r.get('backend') == 'desktop'; "
                "print('LOCK_REQUEST_' + ('PRESENT' if ok else 'ABSENT'))",
                label="LOCK_REQUEST",
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
            _require_guest_capability(
                child,
                "import sys; sys.path.insert(0,'/usr/lib/tether-os'); "
                "from app.gui_backend import ShellRpcClient as C,SessionLockedError; "
                "c=C('/run/user/1000/trap-hub-shell.sock'); ns={'ok':False,'c':c}; "
                "exec('try:\\n c.request(\\'state\\')\\nexcept SessionLockedError:\\n ns[\\'ok\\']=True',"
                "{'SessionLockedError':SessionLockedError,'ns':ns,'c':c}); ok=ns['ok']; "
                "print('RPC_LOCKED_' + ('PRESENT' if ok else 'ABSENT'))",
                label="RPC_LOCKED",
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
            _require_guest_capability(
                child,
                "import sys; sys.path.insert(0,'/usr/lib/tether-os'); "
                "from app.gui_backend import ShellRpcClient as C; "
                "c=C('/run/user/1000/trap-hub-shell.sock'); "
                "p=c.request('execute',{'line':'pwd'}).get('stdout',''); "
                "j=c.request('execute',{'line':'jobs'}).get('stdout',''); "
                "ok=p.strip().endswith('/continuity') and 'running' in j; "
                "print('STATE_CONTINUITY_' + ('PRESENT' if ok else 'ABSENT'))",
                label="STATE_CONTINUITY",
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
        if screenshot_path:
            try:
                _capture_framebuffer(monitor_path, screenshot_path)
            except Exception as screenshot_exc:
                print(
                    f"Unable to capture failure framebuffer: {screenshot_exc}",
                    file=sys.stderr,
                )
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
    parser.add_argument("--firmware", choices=("bios", "uefi"), default="bios")
    parser.add_argument("--media", choices=("optical", "usb"), default="optical")
    parser.add_argument("--uefi-code")
    parser.add_argument("--uefi-vars")
    args = parser.parse_args(argv)
    return run_smoke(
        args.iso,
        edition=args.edition,
        timeout=args.timeout,
        boot_budget=args.boot_budget,
        screenshot_path=args.screenshot,
        firmware=args.firmware,
        media=args.media,
        uefi_code=args.uefi_code,
        uefi_vars=args.uefi_vars,
    )


if __name__ == "__main__":
    raise SystemExit(main())
