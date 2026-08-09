"""Optional GTK adapter for the TRAP HUB Command Deck.

GTK is imported lazily so TetherOS Core and desktop Python installations do
not gain a graphical dependency.  Authentication still belongs to the host
session locker, never this UI.
"""

from dataclasses import dataclass
import importlib.util
import os
import sys
import time

from app.session import log_cmd
from app.shell_parser import ShellSyntaxError, parse_line


@dataclass(frozen=True)
class GuiCommandResponse:
    stdout: str
    exit_code: int
    command_id: str = ""


def gui_available():
    return importlib.util.find_spec("gi") is not None


def publish_ready_marker(path):
    """Publish GUI readiness without following attacker-controlled symlinks."""
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    flags |= getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o600)
    try:
        if hasattr(os, "fchmod"):
            os.fchmod(descriptor, 0o600)
        else:
            os.chmod(path, 0o600)
        os.write(descriptor, b"TRAP_HUB_GUI_READY\n")
    finally:
        os.close(descriptor)


def clear_ready_marker(path):
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass


class CommandDeckController:
    """Toolkit-independent adapter shared by GTK and GUI tests."""

    def __init__(self, shell):
        self.shell = shell

    def state(self):
        return self.shell.deck_state()

    def execute(self, line):
        raw = line.strip()
        if not raw:
            return GuiCommandResponse("", 0)
        try:
            parsed = parse_line(raw)
        except ShellSyntaxError as exc:
            return GuiCommandResponse(f"syntax error: {exc}\n", 2)
        if parsed.background:
            return GuiCommandResponse(
                "Use the terminal edition to start managed background jobs.\n", 2
            )
        if parsed.redirect_path:
            return GuiCommandResponse(
                "GUI redirection is not enabled in the feasibility edition.\n", 2
            )
        with self.shell._command_lock:
            output = self.shell._run_pipeline(parsed.commands)
            result = self.shell._last_result
        log_cmd(raw, output)
        return GuiCommandResponse(
            stdout=output,
            exit_code=result.exit_code if result else 0,
            command_id=result.command_id if result else "",
        )

    def lock(self):
        return self.shell._locker.lock()


class GtkCommandDeck:
    def __init__(self, controller, *, windowed=False):
        import gi

        gi.require_version("Gtk", "3.0")
        from gi.repository import Gdk, GLib, Gtk

        self.GLib = GLib
        self.Gtk = Gtk
        self.controller = controller
        self._last_activity = time.monotonic()
        self._locking = False
        self.window = Gtk.Window(title="TRAP HUB // Command Deck")
        self.window.set_default_size(1180, 760)
        self.window.connect("destroy", lambda *_args: Gtk.main_quit())
        self.window.add_events(
            Gdk.EventMask.KEY_PRESS_MASK |
            Gdk.EventMask.POINTER_MOTION_MASK |
            Gdk.EventMask.BUTTON_PRESS_MASK |
            Gdk.EventMask.SCROLL_MASK
        )
        self.window.connect("event", self._record_activity)
        if not windowed:
            self.window.fullscreen()

        css = Gtk.CssProvider()
        css.load_from_data(b"""
            window { background: #070b12; color: #d7e2f0; }
            #header { background: #0d1522; border-bottom: 1px solid #1bc9a5; padding: 16px; }
            #brand { color: #42f5c5; font-size: 22px; font-weight: 700; }
            #status { color: #8094ad; }
            textview { background: #05080d; color: #d7e2f0; font-family: monospace; font-size: 13px; }
            entry { background: #0d1522; color: #f4f8ff; border: 1px solid #253954; padding: 10px; }
            button { background: #10263a; color: #42f5c5; border: 1px solid #1bc9a5; padding: 9px 16px; }
        """)
        Gtk.StyleContext.add_provider_for_screen(
            self.window.get_screen(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        header.set_name("header")
        brand = Gtk.Label(label="TRAP HUB // COMMAND DECK")
        brand.set_name("brand")
        brand.set_xalign(0)
        self.status = Gtk.Label(label="INITIALIZING")
        self.status.set_name("status")
        self.status.set_xalign(1)
        header.pack_start(brand, True, True, 0)
        header.pack_end(self.status, True, True, 0)
        root.pack_start(header, False, False, 0)

        scroller = Gtk.ScrolledWindow()
        self.output = Gtk.TextView()
        self.output.set_editable(False)
        self.output.set_cursor_visible(False)
        self.output.set_monospace(True)
        scroller.add(self.output)
        root.pack_start(scroller, True, True, 12)

        command_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.entry = Gtk.Entry()
        self.entry.set_placeholder_text("Enter a TRAP HUB command")
        self.entry.connect("activate", self._run_command)
        run_button = Gtk.Button(label="RUN")
        run_button.connect("clicked", self._run_command)
        lock_button = Gtk.Button(label="LOCK SESSION")
        lock_button.connect("clicked", self._lock_session)
        command_row.pack_start(self.entry, True, True, 0)
        command_row.pack_start(run_button, False, False, 0)
        command_row.pack_start(lock_button, False, False, 0)
        root.pack_end(command_row, False, False, 12)

        self.window.add(root)
        self._append("TRAP HUB graphical feasibility edition ready.\n")
        self._refresh_status()
        GLib.timeout_add_seconds(1, self._refresh_status)

    def _append(self, text):
        buffer = self.output.get_buffer()
        buffer.insert(buffer.get_end_iter(), text)
        mark = buffer.create_mark(None, buffer.get_end_iter(), False)
        self.output.scroll_mark_onscreen(mark)

    def _refresh_status(self):
        state = self.controller.state()
        route = "VERIFIED" if state.tor_verified else "UNVERIFIED"
        self.status.set_text(
            f"TOR {route}  //  JOBS {state.running_jobs}  //  "
            f"LOCK {'READY' if state.lock_ready else 'UNAVAILABLE'}"
        )
        if (
            state.lock_ready
            and not self._locking
            and time.monotonic() - self._last_activity >= state.lock_timeout_seconds
        ):
            self._lock_session()
        return True

    def _record_activity(self, *_args):
        self._last_activity = time.monotonic()
        return False

    def _run_command(self, *_args):
        line = self.entry.get_text().strip()
        if not line:
            return
        self.entry.set_text("")
        self._append(f"\n> {line}\n")
        response = self.controller.execute(line)
        self._append(response.stdout or f"[exit {response.exit_code}]\n")
        self._refresh_status()

    def _lock_session(self, *_args):
        if self._locking:
            return
        self._locking = True
        self._append("\n[requesting trusted operating-system lock]\n")
        try:
            result = self.controller.lock()
            if not result.success:
                self._append(f"[lock failed: {result.message}]\n")
            elif result.backend == "desktop":
                self.Gtk.main_quit()
        finally:
            self._last_activity = time.monotonic()
            self._locking = False

    def run(self):
        self.window.show_all()
        self.entry.grab_focus()
        while self.Gtk.events_pending():
            self.Gtk.main_iteration_do(False)
        ready_file = os.environ.get("TETHER_GUI_READY_FILE")
        if ready_file:
            publish_ready_marker(ready_file)
        try:
            self.Gtk.main()
        finally:
            if ready_file:
                clear_ready_marker(ready_file)
        return 0


def main(argv=None):
    args = list(argv or [])
    if not gui_available():
        print(
            "TRAP HUB GUI is unavailable: install GTK 3 and PyGObject, or use the Core terminal edition.",
            file=sys.stderr,
        )
        return 2
    unknown = [arg for arg in args if arg != "--windowed"]
    if unknown:
        print("usage: tether --gui [--windowed]", file=sys.stderr)
        return 2
    from app.shell import TetherShell

    shell = TetherShell()
    controller = CommandDeckController(shell)
    try:
        return GtkCommandDeck(controller, windowed="--windowed" in args).run()
    finally:
        shell.jobs.shutdown()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
