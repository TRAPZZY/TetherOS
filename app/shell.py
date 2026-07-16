"""shell.py -- TRAP HUB CLI shell inspired by Claude Code's terminal design"""
import sys
import os as real_os
import time
import json
import shutil
import socket
import subprocess
import io
import re as _re
from collections import deque

sys.path.insert(0, real_os.path.dirname(real_os.path.dirname(real_os.path.abspath(__file__))))

from kernel.rotator import Rotator
from kernel.probe import Probe
from lib.network import check_port, detect_system_tor
from lib.pidfile import is_running, stop_daemon, read_state
from app.banner import (
    boot_sequence, clear, hide_cursor, show_cursor, reset_color, spinner,
)
from app.theme import theme, list_themes
from app.session import log_cmd, view_log
from app.tools import Tools
from app.vfs import VirtualFS
from app.commands import register_all as register_all_commands

HOSTNAME = "trap-hub"
USERNAME = "root"

_BG = "\033[40m"
_RESET_BG = "\033[0m"
_SAVE = "\033[s"
_RESTORE = "\033[u"
_CLR_EOL = "\033[K"


def _strip_ansi(s):
    return _re.sub(r'\033\[[0-9;]*m', '', s)


def _col(k, text):
    return f"{theme.c(k)}{text}{theme.c('reset')}"


def _dim(text):
    return f"\033[2m{text}\033[0m"


class StatusBar:
    def __init__(self, shell):
        self.shell = shell

    def render_str(self, line):
        w = shutil.get_terminal_size().columns
        ip = self.shell._current_ip or "?.?.?.?"
        tor_ok = detect_system_tor().get("detected", False)
        prot = "\033[32mPROTECTED\033[0m" if tor_ok else "\033[31mEXPOSED\033[0m"
        tn = ["LOW", "GUARDED", "ELEVATED", "HIGH", "SEVERE"][min(self.shell._threat_level, 4)]
        th_clr = "\033[32m" if self.shell._threat_level < 2 else "\033[33m" if self.shell._threat_level < 4 else "\033[31m"
        theme_name = theme.get()["name"]

        left = f" TRAP HUB \033[36mv1.0.0\033[0m  IP:\033[32m{ip}\033[0m  R:{self.shell._rotation_count}"
        right = f"{prot}  TH:{th_clr}{tn}\033[0m  \033[90m{theme_name}\033[0m "

        mid = " " * (w - len(_strip_ansi(left)) - len(_strip_ansi(right)))
        full = left + mid + right
        full_stripped = _strip_ansi(full)

        if len(full_stripped) > w:
            full = full[:w]

        return f"\033[{line};1H{_BG} {full_stripped[:w-1]}{_RESET_BG}{_CLR_EOL}"

    def render(self):
        h = shutil.get_terminal_size().lines
        sys.stdout.write(self.render_str(h))
        sys.stdout.flush()


class LineEditor:
    def __init__(self, shell):
        self.shell = shell
        self.buffer = ""
        self.history = []
        self.history_pos = -1
        self.cursor_pos = 0
        self.tab_matches = []
        self.tab_index = -1

    def prompt_str(self):
        return f"\033[36m>\033[0m "

    def _ensure_status_bar(self):
        self.shell._status_bar.render()

    def _clear_line(self):
        h = shutil.get_terminal_size().lines
        sys.stdout.write(f"\033[{h - 1};1H\033[2K")
        sys.stdout.flush()

    def read(self):
        self.buffer = ""
        self.cursor_pos = 0
        self.history_pos = len(self.history)
        self.tab_matches = []
        self.tab_index = -1
        h = shutil.get_terminal_size().lines
        prompt = self.prompt_str()
        sys.stdout.write(f"\033[{h - 1};1H\033[2K{prompt}")
        sys.stdout.flush()
        if real_os.name == "nt":
            return self._read_win()
        else:
            return self._read_unix()

    def _redraw_input(self):
        h = shutil.get_terminal_size().lines
        prompt = self.prompt_str()
        plen = len(_strip_ansi(prompt))
        sys.stdout.write(f"\033[{h - 1};1H\033[2K{prompt}{self.buffer}")
        ccol = plen + self.cursor_pos + 1
        sys.stdout.write(f"\033[{h - 1};{ccol}H")
        sys.stdout.flush()

    def _read_win(self):
        import msvcrt
        while True:
            ch = msvcrt.getch()
            if ch == b'\r':
                print()
                cmd = self.buffer.strip()
                if cmd:
                    self.history.append(cmd)
                self.history_pos = len(self.history)
                return cmd
            elif ch == b'\x08':
                if self.cursor_pos > 0:
                    self.buffer = self.buffer[:self.cursor_pos-1] + self.buffer[self.cursor_pos:]
                    self.cursor_pos -= 1
                    self._redraw_input()
            elif ch == b'\xe0':
                arrow = msvcrt.getch()
                if arrow == b'H':
                    if self.history_pos > 0:
                        self.history_pos -= 1
                        self.buffer = self.history[self.history_pos]
                        self.cursor_pos = len(self.buffer)
                        self._redraw_input()
                elif arrow == b'P':
                    if self.history_pos < len(self.history) - 1:
                        self.history_pos += 1
                        self.buffer = self.history[self.history_pos]
                        self.cursor_pos = len(self.buffer)
                        self._redraw_input()
                    else:
                        self.history_pos = len(self.history)
                        self.buffer = ""
                        self.cursor_pos = 0
                        self._redraw_input()
                elif arrow == b'K':
                    if self.cursor_pos > 0:
                        self.cursor_pos -= 1
                        sys.stdout.write('\b')
                        sys.stdout.flush()
                elif arrow == b'M':
                    if self.cursor_pos < len(self.buffer):
                        sys.stdout.write(self.buffer[self.cursor_pos])
                        self.cursor_pos += 1
                        sys.stdout.flush()
                elif arrow == b'I':
                    self.shell._scroll(-self.shell._scroll_page)
                elif arrow == b'Q':
                    self.shell._scroll(self.shell._scroll_page)
            elif ch == b'\t':
                self._handle_tab()
            else:
                try:
                    char = ch.decode('utf-8')
                    if char.isprintable():
                        self.buffer = self.buffer[:self.cursor_pos] + char + self.buffer[self.cursor_pos:]
                        self.cursor_pos += 1
                        self._redraw_input()
                except:
                    pass

    def _read_unix(self):
        import termios, tty, select
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            while True:
                if select.select([sys.stdin], [], [], 0.1)[0]:
                    ch = sys.stdin.read(1)
                    if ch in ('\r', '\n'):
                        h = shutil.get_terminal_size().lines
                        sys.stdout.write(f"\033[{h - 1};1H\033[2K")
                        sys.stdout.flush()
                        cmd = self.buffer.strip()
                        if cmd:
                            self.history.append(cmd)
                        self.history_pos = len(self.history)
                        return cmd
                    elif ch == '\x7f':
                        if self.cursor_pos > 0:
                            self.buffer = self.buffer[:self.cursor_pos-1] + self.buffer[self.cursor_pos:]
                            self.cursor_pos -= 1
                            self._redraw_input()
                    elif ch == '\t':
                        self._handle_tab()
                    elif ch == '\x1b':
                        seq = sys.stdin.read(2)
                        if seq == '[A':
                            if self.history_pos > 0:
                                self.history_pos -= 1
                                self.buffer = self.history[self.history_pos]
                                self.cursor_pos = len(self.buffer)
                                self._redraw_input()
                        elif seq == '[B':
                            if self.history_pos < len(self.history) - 1:
                                self.history_pos += 1
                                self.buffer = self.history[self.history_pos]
                                self.cursor_pos = len(self.buffer)
                                self._redraw_input()
                            else:
                                self.history_pos = len(self.history)
                                self.buffer = ""
                                self.cursor_pos = 0
                                self._redraw_input()
                        elif seq == '[D':
                            if self.cursor_pos > 0:
                                self.cursor_pos -= 1
                        elif seq == '[C':
                            if self.cursor_pos < len(self.buffer):
                                self.cursor_pos += 1
                        elif seq == '[5':
                            if sys.stdin.read(1) == '~':
                                self.shell._scroll(-self.shell._scroll_page)
                        elif seq == '[6':
                            if sys.stdin.read(1) == '~':
                                self.shell._scroll(self.shell._scroll_page)
                    elif ch.isprintable():
                        self.buffer = self.buffer[:self.cursor_pos] + ch + self.buffer[self.cursor_pos:]
                        self.cursor_pos += 1
                        self._redraw_input()
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
        return ""

    def _handle_tab(self):
        if not self.tab_matches:
            words = self.buffer.split()
            if not self.buffer or self.buffer[-1] == " ":
                self.tab_matches = []
                self.tab_index = -1
                return
            prefix = words[-1] if self.buffer.strip() else ""
            candidates = set()
            candidates.update(k for k in self.shell._commands if k.startswith(prefix))
            candidates.update(k for k in self.shell._aliases if k.startswith(prefix))
            candidates.add("..")
            if prefix.startswith("/") or prefix.startswith(".") or "/" in prefix or not prefix:
                try:
                    v = self.shell._vfs
                    dp = prefix.rsplit("/", 1)
                    base = v.resolve(dp[0]) if len(dp) > 1 and dp[0] else v.cwd
                    pn = dp[1] if len(dp) > 1 else prefix
                    if v.exists(base) and v.is_dir(base):
                        for child in v.listdir(base) or []:
                            if child.startswith(pn):
                                full = (dp[0] + "/" + child) if len(dp) > 1 and dp[0] else child
                                candidates.add(full)
                except:
                    pass
            sc = sorted(candidates)
            if len(sc) == 1:
                rest = sc[0][len(prefix):]
                self.buffer += rest
                self.cursor_pos = len(self.buffer)
                self._redraw_input()
                self.tab_matches = []
                return
            self.tab_matches = sc
            self.tab_index = -1
        if self.tab_matches:
            self.tab_index = (self.tab_index + 1) % len(self.tab_matches)
            match = self.tab_matches[self.tab_index]
            words = self.buffer.split()
            if words:
                words[-1] = match
            else:
                words = [match]
            self.buffer = " ".join(words)
            self.cursor_pos = len(self.buffer)
            self._redraw_input()


class TetherShell:
    def __init__(self):
        self.running = False
        self._start_time = None
        self.rotator = Rotator()
        self.probe = Probe()
        self._rotation_count = 0
        self._current_ip = None
        self._tools = Tools()
        self._tor_status = "CHECKING"
        self._interval = 60
        self._threat_level = 0
        self._vfs = VirtualFS()
        self._editor = LineEditor(self)
        self._status_bar = StatusBar(self)
        self._commands = {}
        self._aliases = {}
        self._register_commands()

        self._out_buf = []
        self._out_lines = deque(maxlen=2000)
        self._scroll_ofs = 0
        self._scroll_page = 10
        self._header_h = 6
        self._max_scroll_lines = 2000

    def _register_commands(self):
        self._aliases = {
            "q": "exit", "quit": "exit", "cls": "clear",
            "ll": "ls -la", "la": "ls -a", "..": "cd ..",
            "newnym": "rotate", "stat": "status", "whereami": "geoip",
            "speed": "speedtest", "ipconfig": "ifconfig", "ver": "uname -a",
            "?" : "help", "ththeme": "theme",
        }
        self._commands = {
            "cd": self._cmd_cd, "pwd": self._cmd_pwd, "ls": self._cmd_ls,
            "cat": self._cmd_cat, "head": self._cmd_head, "tail": self._cmd_tail,
            "touch": self._cmd_touch, "mkdir": self._cmd_mkdir,
            "rm": self._cmd_rm, "rmdir": self._cmd_rmdir,
            "cp": self._cmd_cp, "mv": self._cmd_mv,
            "chmod": self._cmd_chmod, "chown": self._cmd_chown,
            "find": self._cmd_find, "du": self._cmd_du,
            "tree": self._cmd_tree, "stat": self._cmd_vstat,
            "whoami": self._cmd_whoami, "id": self._cmd_whoami,
            "uname": self._cmd_uname, "clear": self._cmd_clear,
            "echo": self._cmd_echo, "date": self._cmd_date,
            "uptime": self._cmd_uptime, "hostname": self._cmd_hostname,
            "env": self._cmd_env, "printenv": self._cmd_env,
            "which": self._cmd_which, "ps": self._cmd_ps, "top": self._cmd_top,
            "ip": self._cmd_ip, "myip": self._cmd_ip,
            "ping": self._cmd_ping, "dnsleak": self._cmd_dnsleak,
            "geoip": self._cmd_geoip, "speedtest": self._cmd_speedtest,
            "netstat": self._cmd_netstat, "ss": self._cmd_netstat,
            "ifconfig": self._cmd_ifconfig,
            "curl": self._cmd_curl, "wget": self._cmd_curl,
            "traceroute": self._cmd_traceroute, "tracepath": self._cmd_traceroute,
            "nslookup": self._cmd_nslookup, "dig": self._cmd_nslookup,
            "rotate": self._cmd_rotate, "killswitch": self._cmd_killswitch,
            "status": self._cmd_status, "history": self._cmd_history,
            "help": self._cmd_help, "man": self._cmd_help,
            "exit": self._cmd_exit,
            "sudo": self._cmd_sudo, "su": self._cmd_su,
            "shutdown": self._cmd_shutdown, "reboot": self._cmd_reboot,
            "reset": self._cmd_reset, "banner": self._cmd_banner,
            "theme": self._cmd_theme, "log": self._cmd_log,
            "script": self._cmd_script, "motd": self._cmd_motd,
            "save": self._cmd_save, "restore": self._cmd_restore,
            "cron": self._cmd_cron,
        }
        register_all_commands(self._commands, self._aliases)

    def _out(self, text="", end="\n"):
        self._out_buf.append(str(text) + end)

    def _flush(self):
        if not self._out_buf:
            return
        for line in self._out_buf:
            self._out_lines.append((line, _strip_ansi(line)))
        self._out_buf = []
        self._scroll_ofs = 0
        self._paint()

    def _scroll(self, delta):
        max_ofs = max(0, len(self._out_lines) - 1)
        self._scroll_ofs = max(0, min(max_ofs, self._scroll_ofs + delta))
        self._paint()

    def _draw_header(self):
        w = shutil.get_terminal_size().columns
        sep = _col("primary", "=" * min(w - 2, 54))
        lines = [
            f"  {sep}",
            f"  {_col('primary', 'TRAP HUB')} {_col('accent', 'v1.0.0')}  |  {_col('secondary', 'SECURE TERMINAL')}",
            f"  {sep}",
            f"  {_dim('Type')} {_col('accent', 'help')} {_dim('for commands')}  |  {_col('accent', 'theme list')} {_dim('to change colors')}",
            f"  {_dim(f'{len(self._commands)} built-in commands')}",
            f"  {sep}",
        ]
        for i, line in enumerate(lines):
            sys.stdout.write(f"\033[{1 + i};1H\033[2K{line}\033[K")
        sys.stdout.flush()

    def _paint(self):
        h = shutil.get_terminal_size().lines
        top = self._header_h
        scroll_h = h - top - 2
        if scroll_h < 1:
            scroll_h = 1

        total = len(self._out_lines)
        end = total - self._scroll_ofs
        start = max(0, end - scroll_h)
        visible = list(self._out_lines)[start:end]

        parts = []
        for i, (raw, _) in enumerate(visible):
            parts.append(f"\033[{top + 1 + i};1H\033[2K{raw}")
        for i in range(len(visible), scroll_h):
            parts.append(f"\033[{top + 1 + i};1H\033[2K")

        prompt = "\033[36m>\033[0m "
        parts.append(f"\033[{h - 1};1H\033[2K{prompt}{self._editor.buffer}")
        parts.append(self._status_bar.render_str(h))

        plen = len(_strip_ansi(prompt))
        ccol = plen + self._editor.cursor_pos + 1
        parts.append(f"\033[{h - 1};{ccol}H")

        sys.stdout.write("".join(parts))
        sys.stdout.flush()

    def _info(self, text):
        self._out(f"  {text}")

    def _err(self, text):
        self._out(f"  {_col('warning', text)}")

    def _ok(self, text):
        self._out(f"  {_col('secondary', text)}")

    def _cmd_cd(self, args):
        target = args[0] if args else "~"
        resolved = self._vfs.resolve(target)
        if not self._vfs.exists(resolved):
            self._err(f"cd: {target}: No such directory")
            return
        if not self._vfs.is_dir(resolved):
            self._err(f"cd: {target}: Not a directory")
            return
        self._vfs.cwd = resolved

    def _cmd_pwd(self, args):
        self._out(f"  {self._vfs.cwd}")

    def _cmd_ls(self, args):
        flags = {"all": False, "long": False, "human": False}
        paths = []
        for a in args:
            if a.startswith("-"):
                for f in a.lstrip("-"):
                    if f == "a": flags["all"] = True
                    elif f == "l": flags["long"] = True
                    elif f == "h": flags["human"] = True
            else:
                paths.append(a)
        if not paths:
            paths = ["."]
        for pi, target in enumerate(paths):
            resolved = self._vfs.resolve(target)
            if not self._vfs.exists(resolved):
                self._err(f"ls: cannot access '{target}': No such file")
                continue
            if pi > 0:
                self._out()
            items = []
            if self._vfs.is_dir(resolved):
                if flags["all"] and resolved == self._vfs.cwd:
                    items.append((".", self._vfs.stat(".")))
                    items.append(("..", self._vfs.stat("..")))
                children = self._vfs.listdir(resolved) or []
                for name in sorted(children):
                    path = resolved.rstrip("/") + "/" + name if resolved != "/" else "/" + name
                    s = self._vfs.stat(path)
                    if s:
                        items.append((name, s))
                    elif flags["all"] or not name.startswith("."):
                        items.append((name, {"type": "file", "mode": "?", "size": 0, "mtime": None}))
            else:
                s = self._vfs.stat(resolved)
                name = resolved.rsplit("/", 1)[1] if "/" in resolved else resolved
                items.append((name, s))
            if flags["long"]:
                for name, s in items:
                    if not flags["all"] and name.startswith("."):
                        continue
                    mode = s.get("mode", "?" * 10) if s else "?" * 10
                    size = s.get("size", 0) if s else 0
                    mtime = s.get("mtime", None) if s else None
                    ms = mtime.strftime("%b %d %H:%M") if mtime else "??? ?? ????   "
                    if s and s.get("type") == "dir":
                        name = f"\033[36m{name}/\033[0m"
                    elif s and s.get("type") == "dev":
                        name = f"\033[33m{name}\033[0m"
                    self._out(f"  {mode}  {size:>8}  {ms}  {name}")
            else:
                cols = 4
                cw = max((shutil.get_terminal_size().columns - 4) // cols, 10)
                row = []
                for name, s in items:
                    if not flags["all"] and name.startswith("."):
                        continue
                    display = name
                    if s and s.get("type") == "dir":
                        display = f"\033[36m{name}/\033[0m"
                    elif s and s.get("type") == "dev":
                        display = f"\033[33m{name}\033[0m"
                    row.append(display.ljust(cw))
                    if len(row) == cols:
                        self._out("  " + "".join(row))
                        row = []
                if row:
                    self._out("  " + "".join(row))

    def _cmd_cat(self, args):
        if not args:
            self._out("  usage: cat <file> [...]")
            return
        for fpath in args:
            resolved = self._vfs.resolve(fpath)
            content = self._vfs.read(resolved)
            if content is not None:
                sys.stdout.write(content)
                if not content.endswith("\n"):
                    self._out()
            else:
                rp = real_os.path.abspath(fpath)
                if real_os.path.isfile(rp):
                    try:
                        with open(rp) as f:
                            sys.stdout.write(f.read())
                    except Exception as e:
                        self._err(f"cat: {fpath}: {e}")
                else:
                    self._err(f"cat: {fpath}: No such file")

    def _cmd_head(self, args):
        n = 10
        files = []
        for a in args:
            if a.startswith("-"):
                try:
                    n = int(a.lstrip("-n").strip() or a.lstrip("-"))
                except:
                    pass
            else:
                files.append(a)
        if not files:
            self._out("  usage: head [-n] <file>")
            return
        for fpath in files:
            resolved = self._vfs.resolve(fpath)
            content = self._vfs.read(resolved)
            if content is not None:
                for line in content.split("\n")[:n]:
                    self._out(f"  {line}")
            else:
                self._err(f"head: {fpath}: No such file")

    def _cmd_tail(self, args):
        n = 10
        files = []
        for a in args:
            if a.startswith("-"):
                try:
                    n = int(a.lstrip("-n").strip() or a.lstrip("-"))
                except:
                    pass
            else:
                files.append(a)
        if not files:
            self._out("  usage: tail [-n] <file>")
            return
        for fpath in files:
            resolved = self._vfs.resolve(fpath)
            content = self._vfs.read(resolved)
            if content is not None:
                for line in content.split("\n")[-n:]:
                    self._out(f"  {line}")
            else:
                self._err(f"tail: {fpath}: No such file")

    def _cmd_touch(self, args):
        if not args:
            self._out("  usage: touch <file> [...]")
            return
        for fpath in args:
            if not self._vfs.touch(fpath):
                self._err(f"touch: cannot touch '{fpath}'")

    def _cmd_mkdir(self, args):
        if not args:
            self._out("  usage: mkdir <dir> [...]")
            return
        for d in args:
            if not self._vfs.mkdir(d):
                self._err(f"mkdir: cannot create directory '{d}'")

    def _cmd_rm(self, args):
        if not args:
            self._out("  usage: rm [-rf] <file> [...]")
            return
        recursive = False
        force = False
        targets = []
        for a in args:
            if a in ("-rf", "-fr"): recursive = force = True
            elif a == "-r": recursive = True
            elif a == "-f": force = True
            else: targets.append(a)
        for fpath in targets:
            resolved = self._vfs.resolve(fpath)
            if not self._vfs.exists(resolved):
                if not force:
                    self._err(f"rm: cannot remove '{fpath}': No such file")
                continue
            if self._vfs.is_dir(resolved) and not recursive:
                self._err(f"rm: cannot remove '{fpath}': Is a directory")
                continue
            if self._vfs.is_dir(resolved):
                self._vfs.rmtree(resolved)
            else:
                self._vfs.remove(resolved)

    def _cmd_rmdir(self, args):
        if not args:
            self._out("  usage: rmdir <dir> [...]")
            return
        for d in args:
            resolved = self._vfs.resolve(d)
            if not self._vfs.exists(resolved):
                self._err(f"rmdir: failed to remove '{d}': No such file")
            elif not self._vfs.is_dir(resolved):
                self._err(f"rmdir: failed to remove '{d}': Not a directory")
            elif self._vfs.listdir(resolved):
                self._err(f"rmdir: failed to remove '{d}': Directory not empty")
            else:
                self._vfs.remove(resolved)

    def _cmd_cp(self, args):
        if len(args) < 2:
            self._out("  usage: cp <src> <dst>")
            return
        src = self._vfs.resolve(args[0])
        dst = self._vfs.resolve(args[-1])
        if not self._vfs.exists(src):
            self._err(f"cp: cannot stat '{args[0]}': No such file")
            return
        if self._vfs.is_dir(dst):
            name = src.rsplit("/", 1)[1]
            dst = dst.rstrip("/") + "/" + name
        content = self._vfs.read(src)
        if content is not None:
            self._vfs.write(dst, content)
        else:
            self._vfs.mkdir(dst)
            for child in self._vfs.listdir(src) or []:
                self._cmd_cp([args[0] + "/" + child, dst + "/" + child])

    def _cmd_mv(self, args):
        if len(args) < 2:
            self._out("  usage: mv <src> <dst>")
            return
        src = args[0]
        dst = args[-1]
        resolved_dst = self._vfs.resolve(dst)
        if self._vfs.is_dir(resolved_dst):
            name = src.rsplit("/", 1)[1] if "/" in src else src
            dst = dst.rstrip("/") + "/" + name
        if not self._vfs.rename(src, dst):
            self._err(f"mv: cannot move '{src}' to '{dst}'")

    def _cmd_chmod(self, args):
        if len(args) < 2:
            self._out("  usage: chmod <mode> <file>")
            return
        self._out(f"  chmod: {args[0]} on {args[1]} (virtual, accepted)")

    def _cmd_chown(self, args):
        if len(args) < 2:
            self._out("  usage: chown <user>:<group> <file>")
            return
        self._out(f"  chown: {args[0]} on {args[1]} (virtual, accepted)")

    def _cmd_find(self, args):
        path = "."
        name = None
        i = 0
        while i < len(args):
            if args[i] == "-name" and i + 1 < len(args):
                name = args[i + 1]
                i += 2
            elif args[i].startswith("-"):
                i += 1
            else:
                path = args[i]
                i += 1
        if not name:
            self._out("  usage: find <path> -name <pattern>")
            return
        for r in self._vfs.find(path, name):
            self._out(f"  {r}")

    def _cmd_du(self, args):
        path = args[0] if args else "."
        resolved = self._vfs.resolve(path)
        self._out(f"  {self._vfs.du(resolved):>8}  {path}")

    def _cmd_tree(self, args):
        path = args[0] if args else "."
        resolved = self._vfs.resolve(path)
        if not self._vfs.is_dir(resolved):
            self._err(f"tree: {path}: Not a directory")
            return
        self._out(f"  {path}")
        self._print_tree(resolved, "", "")

    def _print_tree(self, path, prefix, cp):
        children = self._vfs.listdir(path) or []
        for i, name in enumerate(sorted(children)):
            is_last = i == len(children) - 1
            conn = "\u2514\u2500\u2500 " if is_last else "\u251c\u2500\u2500 "
            cp2 = path.rstrip("/") + "/" + name if path != "/" else "/" + name
            s = self._vfs.stat(cp2)
            display = f"\033[36m{name}/\033[0m" if s and s.get("type") == "dir" else name
            self._out(f"  {prefix}{conn}{display}")
            if s and s.get("type") == "dir":
                self._print_tree(cp2, prefix + ("    " if is_last else "\u2502   "), cp)

    def _cmd_vstat(self, args):
        if not args:
            self._out("  usage: stat <file>")
            return
        resolved = self._vfs.resolve(args[0])
        s = self._vfs.stat(resolved)
        if not s:
            self._err(f"stat: cannot stat '{args[0]}': No such file")
            return
        self._out(f"  File: {resolved}")
        self._out(f"  Size: {s.get('size', 0)}")
        self._out(f"  Type: {s.get('type', '?')}")
        self._out(f"  Mode: {s.get('mode', '?')}")
        if s.get("mtime"):
            self._out(f"  Mtime: {s['mtime'].strftime('%Y-%m-%d %H:%M:%S')}")

    def _cmd_whoami(self, args):
        self._ok(f"{USERNAME}")
        self._out(_dim("  (identity protected by Tor network)"))

    def _cmd_uname(self, args):
        al = [a.lower() for a in args]
        if "-a" in al or "--all" in al or not args:
            info = self._tools.system_info()
            self._out(f"  TetherOS {info.get('machine', 'x86_64')}")
            self._out(f"  Kernel: Tether OS 1.0.0 (Tor Runtime)")
            self._out(f"  Hostname: {HOSTNAME}")

    def _cmd_clear(self, args):
        clear()
        self._draw_header()
        self._out_lines.clear()
        self._out_buf = []
        self._scroll_ofs = 0

    def _cmd_echo(self, args):
        self._out("  " + " ".join(args))

    def _cmd_date(self, args):
        self._out(f"  {time.strftime('%a %b %d %H:%M:%S %Z %Y')}")

    def _cmd_uptime(self, args):
        if not self._start_time:
            self._out("  uptime: 0s")
            return
        elapsed = int(time.time() - self._start_time)
        days = elapsed // 86400
        hours = (elapsed % 86400) // 3600
        mins = (elapsed % 3600) // 60
        secs = elapsed % 60
        pts = []
        if days: pts.append(f"{days}d")
        if hours: pts.append(f"{hours}h")
        pts.append(f"{mins}m")
        pts.append(f"{secs}s")
        tn = ["LOW", "GUARDED", "ELEVATED", "HIGH", "SEVERE"][min(self._threat_level, 4)]
        self._ok(f"up {' '.join(pts)},  {self._rotation_count} rotations  |  threat: {tn}")

    def _cmd_hostname(self, args):
        self._out(f"  {HOSTNAME}")

    def _cmd_env(self, args):
        for k, v in sorted(real_os.environ.items()):
            if any(s in k.lower() for s in ["tor", "tether", "proxy", "socks", "path"]):
                self._ok(f"{k}={v}")

    def _cmd_which(self, args):
        if not args:
            return
        for cmd in args:
            if cmd in self._commands:
                self._ok(f"{cmd}: built-in")
            elif cmd in self._aliases:
                self._out(f"  {cmd}: aliased to {self._aliases[cmd]}")
            else:
                ep = shutil.which(cmd)
                if ep:
                    self._out(f"  {cmd}: {ep}")
                else:
                    self._err(f"{cmd}: not found")

    def _cmd_ps(self, args):
        self._out(f"  {'PID':6} {'USER':10} {'CPU%':6} {'MEM%':6} {'COMMAND':24}")
        self._out(f"  {'-'*6} {'-'*10} {'-'*6} {'-'*6} {'-'*24}")
        tor_ok = detect_system_tor().get("detected", False)
        for pid, user, cpu, mem, cmd in [
            ("1", USERNAME, "0.0", "1.2", "tether-os-kernel"),
            ("2", USERNAME, "0.1", "0.8", "tor-rotator"),
            ("3", USERNAME, "0.0", "0.3", "ip-scheduler"),
            *([("4", "debian-tor", "0.5", "2.1", "tor-daemon")] if tor_ok else []),
        ]:
            self._out(f"  {pid:6} {user:10} {cpu:6} {mem:6} {cmd:24}")

    def _cmd_top(self, args):
        clear()
        self._out(_col("primary", "  TRAP HUB // TASK MANAGER (q to quit)"))
        try:
            while True:
                ip = self._current_ip or self.probe.get_current_ip() or "WAITING"
                tor_ok = detect_system_tor().get("detected", False)
                up = int(time.time() - (self._start_time or time.time()))
                up_str = f"{up//3600:02d}:{(up%3600)//60:02d}:{up%60:02d}"
                self._out(f"\033[H", end="")
                self._ok(f"top - {time.strftime('%H:%M:%S')} up {up_str}")
                self._out()
                self._out(f"  {'PID':6} {'USER':10} {'CPU%':6} {'MEM%':6} {'COMMAND':24}")
                self._out(f"  {'-'*6} {'-'*10} {'-'*6} {'-'*6} {'-'*24}")
                for pid, user, cpu, mem, cmd in [
                    ("1", USERNAME, "0.0", "1.2", "tether-os-kernel"),
                    ("2", USERNAME, "0.1", "0.8", "tor-rotator"),
                    ("3", USERNAME, "0.0", "0.3", "ip-scheduler"),
                ]:
                    self._out(f"  {pid:6} {user:10} {cpu:6} {mem:6} {cmd:24}")
                if tor_ok:
                    self._out(f"  {'4':6} {'debian-tor':10} {'0.5':6} {'2.1':6} {'tor-daemon':24}")
                self._out()
                self._info(f"IP: {ip}  |  Rotations: {self._rotation_count}")
                for _ in range(20):
                    if not self.running:
                        return
                    time.sleep(0.1)
        except KeyboardInterrupt:
            pass

    def _cmd_ip(self, args):
        ip = self._current_ip or self.probe.get_current_ip() or "UNKNOWN"
        self._ok(ip)

    def _cmd_ifconfig(self, args):
        info = self._tools.mac_info()
        if "adapters" in info:
            for a in info["adapters"]:
                name = a.get("name", "?")
                mac = a.get("mac", "N/A")
                ip = a.get("ip", "N/A")
                self._out(f"  \033[36m{name}\033[0m")
                self._out(f"    inet {ip}  netmask 255.255.255.0")
                self._out(f"    ether {mac}")
                self._out()
        else:
            self._out(json.dumps(info, indent=2))

    def _cmd_ping(self, args):
        if not args:
            self._out("  usage: ping <hostname>")
            return
        host = args[0]
        self._info(f"PING {host} via Tor...")
        start = time.time()
        try:
            import urllib.request
            ph = urllib.request.ProxyHandler({
                "http": "socks5h://127.0.0.1:9050",
                "https": "socks5h://127.0.0.1:9050",
            })
            opener = urllib.request.build_opener(ph)
            target = f"https://{host}" if "." in host else "https://httpbin.org/ip"
            opener.open(target, timeout=10)
            elapsed = (time.time() - start) * 1000
            self._ok(f"Reply from {host}: {elapsed:.1f}ms (via Tor)")
        except Exception as e:
            self._err(f"Request timeout for {host}")

    def _cmd_dnsleak(self, args):
        self._info("Scanning for DNS leaks...")
        for r in self._tools.dns_leak_test():
            st = _col("secondary", "[OK]") if not r.get("leak") else _col("warning", "[LEAK]")
            url = r.get("url", "?")
            ip = r.get("ip", r.get("error", "?"))
            self._out(f"  {st}  {url} -> {ip}")

    def _cmd_geoip(self, args):
        ip = args[0] if args else None
        self._info("Tracing geolocation...")
        data = self._tools.geo_lookup(ip)
        if "error" in data:
            self._err(f"Error: {data['error']}")
        else:
            if data.get("proxy"):
                self._info("[!] Proxy/VPN detected")
            self._ok(f"IP:      {data.get('query', '?')}")
            self._ok(f"Country: {data.get('country', '?')}")
            self._ok(f"Region:  {data.get('regionName', '?')}")
            self._ok(f"City:    {data.get('city', '?')}")
            self._ok(f"ISP:     {data.get('isp', '?')}")
            self._ok(f"Org:     {data.get('org', '?')}")

    def _cmd_speedtest(self, args):
        self._info("Measuring throughput via Tor...")
        r = self._tools.speed_test()
        if "error" in r:
            self._err(f"Error: {r['error']}")
        else:
            self._ok(f"Downloaded: {r.get('download_kb', 0)} KB")
            self._ok(f"Time:       {r.get('time_seconds', 0)}s")
            self._ok(f"Speed:      {r.get('speed_kbps', 0)} KB/s")

    def _cmd_netstat(self, args):
        socks = check_port(9050)
        ctrl = check_port(9051)
        self._out(f"  {'PROTO':10} {'LOCAL':24} {'REMOTE':24} {'STATE':12}")
        self._out(f"  {'-'*10} {'-'*24} {'-'*24} {'-'*12}")
        ip = self._current_ip or "?"
        ss = _col("secondary", "OPEN") if socks else _col("warning", "CLOSED")
        cs = _col("secondary", "OPEN") if ctrl else _col("warning", "CLOSED")
        self._out(f"  {'SOCKS5':10} {'127.0.0.1:9050':24} {'Tor Network':24} {ss}")
        self._out(f"  {'CONTROL':10} {'127.0.0.1:9051':24} {'Tor Daemon':24} {cs}")
        self._out(f"  {'EXTERNAL':10} {'[tor]':24} {ip:24} {_col('secondary', 'ESTABLISHED')}")

    def _cmd_curl(self, args):
        if not args:
            self._out("  usage: curl <url>")
            return
        url = args[0]
        self._info(f"Fetching {url} via Tor...")
        try:
            import urllib.request
            ph = urllib.request.ProxyHandler({
                "http": "socks5h://127.0.0.1:9050",
                "https": "socks5h://127.0.0.1:9050",
            })
            opener = urllib.request.build_opener(ph)
            resp = opener.open(url, timeout=15)
            data = resp.read().decode("utf-8", errors="replace")
            for line in data.split("\n")[:20]:
                self._out(f"  {line}")
            if len(data.split("\n")) > 20:
                self._info(f"... (truncated, {len(data)} bytes)")
        except Exception as e:
            self._err(f"curl: {e}")

    def _cmd_traceroute(self, args):
        self._info("Trace to destination via Tor:")
        self._out(f"   1  {_col('secondary', self._current_ip or '?.?.?.?')}  (entry guard)")
        self._out(f"   2  {_col('secondary', '***.***.***.***')}  (middle relay)")
        self._out(f"   3  {_col('secondary', '***.***.***.***')}  (exit node)")
        self._out(f"   4  {_col('accent', 'DESTINATION')}  (anonymized)")

    def _cmd_nslookup(self, args):
        if not args:
            self._out("  usage: nslookup <hostname>")
            return
        host = args[0]
        self._info(f"Resolving {host} via Tor DNS...")
        try:
            import urllib.request
            ph = urllib.request.ProxyHandler({
                "http": "socks5h://127.0.0.1:9050",
                "https": "socks5h://127.0.0.1:9050",
            })
            opener = urllib.request.build_opener(ph)
            resp = opener.open(f"https://dns.google/resolve?name={host}&type=A", timeout=10)
            data = json.loads(resp.read().decode())
            for ans in data.get("Answer", []):
                self._ok(f"{ans.get('name')} -> {ans.get('data')} (TTL={ans.get('TTL')})")
        except Exception as e:
            try:
                ip = socket.gethostbyname(host)
                self._ok(f"{host} -> {ip}")
            except:
                self._err(f"nslookup: {host}: Host not found")

    def _cmd_rotate(self, args):
        self._info("Requesting new Tor circuit...")
        result = self.rotator.rotate()
        if result["success"]:
            self._rotation_count += 1
            self._current_ip = result["new_ip"]
            self._threat_level = min(self._threat_level + 1, 4)
            self._ok(f"{result.get('old_ip', '?')} -> {result['new_ip']}")
            self._ok(f"Rotation #{self._rotation_count}")
        else:
            self._err("Rotation failed -- Tor control port unavailable?")

    def _cmd_killswitch(self, args):
        self._info("Engaging kill switch...")
        ks = self._tools.kill_switch(True)
        if "error" in ks:
            self._info(f"{ks['error']} -- simulated")
        self._ok("Non-Tor traffic blocked.")

    def _cmd_status(self, args):
        sys_tor = detect_system_tor()
        tor_ok = sys_tor["detected"]
        ip = self._current_ip or self.probe.get_current_ip() or "UNKNOWN"
        tn = ["LOW", "GUARDED", "ELEVATED", "HIGH", "SEVERE"][min(self._threat_level, 4)]
        self._out(_col("primary", "  TRAP HUB SYSTEM STATUS"))
        self._out(f"  External IP:      {_col('secondary', ip)}")
        self._out(f"  Tor Circuit:      {_col('secondary', 'ACTIVE (3 hops)') if tor_ok else _col('warning', 'DISCONNECTED')}")
        self._out(f"  Rotations:        {_col('warning', str(self._rotation_count))}")
        self._out(f"  Threat Level:     {_col('warning' if self._threat_level >= 2 else 'secondary', tn)}")
        self._out(f"  Anonymity:        {_col('secondary', 'PROTECTED') if tor_ok else _col('warning', 'EXPOSED')}")
        ks = _col("warning", "ENGAGED") if real_os.environ.get("TETHER_KILLSWITCH") else _col("secondary", "STANDBY")
        self._out(f"  Kill Switch:      {ks}")
        self._out(f"  Theme:            {_col('accent', theme.get()['name'])}")

    def _cmd_history(self, args):
        for i, c in enumerate(self._editor.history, 1):
            self._out(f"  {i:4}  {c}")

    def _cmd_help(self, args):
        clear()
        w = shutil.get_terminal_size().columns
        self._out(_col("primary", f"  {'=' * min(w - 2, 60)}"))
        self._out(_col("primary", f"  TRAP HUB // COMMAND REFERENCE ({len(self._commands)} commands)"))
        self._out(_col("primary", f"  {'=' * min(w - 2, 60)}"))
        self._out()
        cats = [
            ("NAVIGATION", ["cd", "pwd", "ls", "find", "tree"]),
            ("FILE OPS", ["cat", "head", "tail", "touch", "mkdir", "rm", "rmdir",
                          "cp", "mv", "chmod", "chown", "du", "stat"]),
            ("SYSTEM", ["whoami", "uname", "uptime", "date", "hostname",
                         "ps", "top", "clear", "echo", "env", "which"]),
            ("NETWORK", ["ip", "ifconfig", "ping", "dnsleak", "geoip",
                          "speedtest", "netstat", "curl", "traceroute", "nslookup"]),
            ("RECON", ["nmap", "dnsrecon", "gobuster", "theharvester",
                        "whatweb", "whois", "enum4linux", "cewl"]),
            ("SCAN", ["nikto", "nuclei"]),
            ("EXPLOIT", ["searchsploit", "hydra", "hash-identifier"]),
            ("WEB", ["wpscan"]),
            ("FORENSICS", ["binwalk", "hexdump", "strings", "exiftool"]),
            ("ANONYMITY", ["proxychains", "macchanger", "anonsurf"]),
            ("WIRELESS", ["iwconfig", "airmon-ng", "airodump-ng"]),
            ("SHELL", ["theme", "log", "script", "motd", "save", "restore", "cron"]),
            ("TETHER OS", ["rotate", "killswitch", "status", "history", "help", "exit"]),
        ]
        for title, cmds in cats:
            self._out(_col("primary", f"  [{title}]"))
            for c in cmds:
                al = [a for a, t in self._aliases.items() if t == c or t.startswith(c + " ")]
                as_ = f"  (aliases: {', '.join(al)})" if al else ""
                self._out(f"    {_col('accent', c.ljust(16))}{as_}")
            self._out()
        self._out(_dim("  Unknown commands fall through to the real system."))
        self._out(_dim("  Use 'script file.th' to run Tether scripts."))
        self._out(_dim("  Use '|' for pipes, '>' and '>>' for redirection."))

    def _cmd_exit(self, args):
        self.running = False

    def _cmd_sudo(self, args):
        if not args:
            self._out("  usage: sudo <command> [args...]")
            return
        self._execute(" ".join(args))

    def _cmd_su(self, args):
        self._ok("Already root. Your anonymity is absolute.")

    def _cmd_shutdown(self, args):
        self._info("Shutting down Tether OS...")
        time.sleep(0.3)
        self.running = False

    def _cmd_reboot(self, args):
        self._info("Rebooting Tether OS...")
        time.sleep(0.3)
        self.running = False

    def _cmd_reset(self, args):
        clear()
        self._vfs = VirtualFS()
        self._ok("Terminal reset. Virtual filesystem restored.")

    def _cmd_banner(self, args):
        show_cursor()
        boot_sequence()
        show_cursor()

    def _cmd_theme(self, args):
        if not args:
            self._out(f"  Current theme: {_col('accent', theme.get()['name'])}")
            self._out(f"  Available: {', '.join(list_themes())}")
            self._out("  Usage: theme <name>")
            return
        name = args[0].lower()
        if name == "list":
            self._out(f"  Available themes: {', '.join(list_themes())}")
        elif name in list_themes():
            theme.set(name)
            self._ok(f"Theme set to: {name}")
        else:
            self._err(f"Unknown theme: {name}")

    def _cmd_log(self, args):
        n = 50
        if args and args[0].lstrip("-").isdigit():
            n = int(args[0].lstrip("-"))
        self._out(_col("accent", f"  Session log (last {n} lines):"))
        self._out()
        for line in view_log(n):
            sys.stdout.write(f"  {line}")

    def _cmd_script(self, args):
        if not args:
            self._out("  usage: script <file.th> [args...]")
            return
        fpath = args[0]
        sa = args[1:]
        resolved = self._vfs.resolve(fpath)
        content = self._vfs.read(resolved)
        if content is None:
            rp = real_os.path.abspath(fpath)
            if real_os.path.isfile(rp):
                try:
                    with open(rp) as f:
                        content = f.read()
                except Exception as e:
                    self._err(f"script: {fpath}: {e}")
                    return
            else:
                self._err(f"script: {fpath}: No such file")
                return
        self._info(f"Running script: {fpath}")
        self._out()
        for line in content.split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if sa:
                for i, a in enumerate(sa):
                    line = line.replace(f"${i+1}", a).replace("$@", " ".join(sa))
            self._out(_dim(f"$ {line}"))
            self._execute(line, _from_script=True)
        self._out()
        self._ok(f"Script complete: {fpath}")

    def _cmd_motd(self, args):
        self._show_motd()

    def _cmd_save(self, args):
        path = real_os.path.join(real_os.path.expanduser("~"), ".tether", "session.json")
        state = {
            "cwd": self._vfs.cwd,
            "rotation_count": self._rotation_count,
            "threat_level": self._threat_level,
            "current_ip": self._current_ip,
            "theme": theme.get()["name"],
            "history": self._editor.history[-100:],
        }
        try:
            with open(path, "w") as f:
                json.dump(state, f, indent=2)
            self._ok(f"Session saved to {path}")
        except Exception as e:
            self._err(f"save: {e}")

    def _cmd_restore(self, args):
        path = real_os.path.join(real_os.path.expanduser("~"), ".tether", "session.json")
        if not real_os.path.isfile(path):
            self._err("No saved session found.")
            return
        try:
            with open(path) as f:
                state = json.load(f)
            if state.get("cwd") and self._vfs.exists(state["cwd"]):
                self._vfs.cwd = state["cwd"]
            self._rotation_count = state.get("rotation_count", 0)
            self._threat_level = state.get("threat_level", 0)
            self._current_ip = state.get("current_ip")
            if state.get("theme") in list_themes():
                theme.set(state["theme"])
            for h in state.get("history", []):
                if h not in self._editor.history:
                    self._editor.history.append(h)
            self._ok(f"Session restored from {path}")
        except Exception as e:
            self._err(f"restore: {e}")

    def _cmd_cron(self, args):
        if not args:
            self._out("  usage: cron <list|add|del|start|stop|status> [options]")
            return
        try:
            from app.commands.cron import _cmd_cron as _cc
            _cc(args)
        except Exception as e:
            self._err(f"cron: {e}")

    def _show_motd(self):
        w = shutil.get_terminal_size().columns
        sep = _col("primary", "=" * min(w - 2, 54))
        self._out(f"  {sep}")
        self._out(f"  {_col('primary', 'TRAP HUB')} {_col('accent', 'v1.0.0')}  |  {_col('secondary', 'SECURE TERMINAL')}")
        self._out(f"  {sep}")
        self._out(f"  {_dim('Type')} {_col('accent', 'help')} {_dim('for commands')}  |  {_col('accent', 'theme list')} {_dim('to change colors')}")
        self._out(f"  {_dim(f'{len(self._commands)} built-in commands')}")
        self._out(f"  {sep}")

    def _execute(self, line, _from_script=False):
        if not line.strip():
            return

        raw = line.strip()
        append_mode = False
        redirect_file = None

        has_pipe = "|" in raw
        if ">>" in raw and (not has_pipe or ">>" not in raw.split("|")[-1]):
            parts = raw.rsplit(">>", 1)
            redirect_file = parts[1].strip()
            raw = parts[0].strip()
            append_mode = True
        elif ">" in raw and (not has_pipe or ">" not in raw.split("|")[-1]):
            parts = raw.rsplit(">", 1)
            redirect_file = parts[1].strip()
            raw = parts[0].strip()

        if "|" in raw:
            segments = [s.strip() for s in raw.split("|")]
            self._execute_pipe(segments)
            return

        parts = raw.split()
        cmd = parts[0].lower()
        args = parts[1:]

        if cmd in self._aliases:
            expanded = self._aliases[cmd]
            if "$@" in expanded or "{}" in expanded:
                expanded = expanded.replace("$@", " ".join(args)).replace("{}", " ".join(args))
            else:
                expanded = expanded + " " + " ".join(args) if args else expanded
            self._execute(expanded, _from_script)
            return

        captured = self._run_captured(cmd, args)
        output, _ = captured

        if redirect_file:
            resolved = self._vfs.resolve(redirect_file)
            existing = self._vfs.read(resolved) or ""
            self._vfs.write(resolved, (existing + output) if append_mode else output)
            return

        if output:
            for line_text in output.split("\n"):
                s = self._strip_ansi(line_text).strip()
                if s:
                    self._out(f"  {line_text.strip()}")

        if not _from_script:
            log_cmd(raw, output)

    def _run_captured(self, cmd, args):
        buf = io.StringIO()
        old = sys.stdout
        sys.stdout = buf
        try:
            if cmd in self._commands:
                try:
                    self._commands[cmd](args)
                except KeyboardInterrupt:
                    sys.stdout.write("\n  Interrupted.")
                except Exception as e:
                    sys.stdout.write(f"\n  {cmd}: {e}")
                    import traceback
                    traceback.print_exc()
            elif cmd == "cd" and not args:
                self._cmd_cd(["~"])
            else:
                self._run_system_captured(cmd, args)
        finally:
            sys.stdout = old
            sys.stdout.flush()
        return buf.getvalue(), None

    def _run_system_captured(self, cmd, args):
        try:
            r = subprocess.run(
                [cmd] + args, capture_output=True, text=True, timeout=15, shell=True,
            )
            if r.returncode == 0:
                for line in r.stdout.split("\n"):
                    sys.stdout.write(f"  {line}\n")
            else:
                stderr = r.stderr.strip() or r.stdout.strip()
                if stderr:
                    for line in stderr.split("\n"):
                        sys.stdout.write(f"  {line}\n")
                else:
                    sys.stdout.write(f"  {cmd}: command not found\n")
        except FileNotFoundError:
            sys.stdout.write(f"  {cmd}: command not found\n")
        except subprocess.TimeoutExpired:
            sys.stdout.write(f"  {cmd}: timed out (15s)\n")
        except Exception as e:
            sys.stdout.write(f"  {cmd}: {e}\n")

    def _execute_pipe(self, segments):
        output = None
        for segment in segments:
            parts = segment.split()
            if not parts:
                continue
            cmd = parts[0].lower()
            args = parts[1:]

            if cmd in self._aliases:
                expanded = self._aliases[cmd]
                if "$@" in expanded or "{}" in expanded:
                    expanded = expanded.replace("$@", " ".join(args)).replace("{}", " ".join(args))
                else:
                    expanded = expanded + " " + " ".join(args) if args else expanded
                    parts = expanded.split()
                    cmd = parts[0].lower()
                    args = parts[1:]

            buf = io.StringIO()
            old = sys.stdout
            sys.stdout = buf
            try:
                if cmd in self._commands:
                    self._commands[cmd](args)
                elif cmd == "cd" and not args:
                    self._cmd_cd(["~"])
                else:
                    self._run_system_captured(cmd, args)
            except Exception as e:
                sys.stdout.write(f"  {cmd}: {e}\n")
            finally:
                sys.stdout = old
            output = buf.getvalue()

        if output:
            for line in output.split("\n"):
                if self._strip_ansi(line).strip():
                    self._out(f"  {line.strip()}")

    def _strip_ansi(self, s):
        return _strip_ansi(s)

    def start(self):
        hide_cursor()
        self.running = True
        self._start_time = time.time()
        boot_sequence()
        clear()
        self._draw_header()
        self._paint()
        try:
            while self.running:
                line = self._editor.read()
                if line.strip():
                    self._execute(line)
                self._flush()
        finally:
            self.shutdown()

    def shutdown(self):
        self.running = False
        show_cursor()
        clear()
        w = shutil.get_terminal_size().columns
        self._out()
        self._out(_col("primary", f"  {'=' * min(w - 2, 50)}"))
        self._out(_col("primary", "  TRAP HUB // SESSION TERMINATED"))
        self._out(_col("primary", f"  {'=' * min(w - 2, 50)}"))
        self._out()
        if self._start_time:
            elapsed = int(time.time() - self._start_time)
            self._out(f"    Duration:   {elapsed // 60}m {elapsed % 60}s")
            self._out(f"    Commands:   {len(self._editor.history)}")
        self._out(f"    Rotations:  {self._rotation_count}")
        self._out()
        self._ok("YOUR IDENTITY REMAINS HIDDEN")
        self._out(_col("primary", "Stay safe out there, operator."))
        self._out()


def main():
    shell = TetherShell()
    shell.start()
