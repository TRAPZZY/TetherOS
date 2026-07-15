# Tether OS Architecture

**Version:** 1.0.0  
**Author:** Trapzzy  
**Design Philosophy:** Unix-inspired — do one thing well, compose via pipes.

## Overview

Tether OS is a privacy tool and penetration testing shell. It automatically
rotates your public IP address using the Tor network, provides 90+ built-in
commands for reconnaissance, exploitation, forensics, and web scanning, and
delivers a Claude Code-inspired terminal interface.

## Layer Architecture

```
+-----------------------------------------------------------+
|                   SHELL LAYER (app/)                        |
|  shell.py  |  banner.py  |  theme.py  |  session.py        |
|  vfs.py    |  tools.py    |  cli.py    |  daemon.py         |
|  commands/  (8 modules, 25+ commands)                      |
+-----------------------------------------------------------+
|                   KERNEL LAYER (kernel/)                    |
|  rotator.py  |  torctl.py  |  probe.py  |  scheduler.py    |
+-----------------------------------------------------------+
|                   LIBRARY LAYER (lib/)                      |
|  network.py  |  pidfile.py                                  |
+-----------------------------------------------------------+
|                   TOR NETWORK                               |
|  SOCKS5 proxy :9050  |  Control port :9051                 |
+-----------------------------------------------------------+
```

## Shell Layer

### app/shell.py — Main REPL

The shell provides a Claude Code-inspired terminal interface with:

- **`>` prompt** — Clean, minimal prompt prefix
- **Bottom status bar** — Persistent bar showing current IP, rotation count, Tor status, threat level, and active theme
- **Pipe support** — `command1 | command2` chains commands, passing stdout as arguments
- **Redirect support** — `>` write, `>>` append to virtual filesystem
- **`.th` scripts** — Positional arg substitution (`$1`-`$N`, `$@`), executed line by line
- **Session persistence** — `save`/`restore` commands write/read JSON state
- **Command registry** — 90+ commands loaded from `app/commands/` modules at startup

### app/banner.py — Boot Sequence

Multi-stage animated boot:

1. **splash_screen()** — Full dark screen, centered hacker frame with bold red "TETHER OS", pulsing ">> TARGET ACQUIRED <<" warning, bottom separator
2. **matrix_rain()** — Classic green digital rain effect (hex character set for Windows cp1252 compatibility)
3. **TRAP_HUB_LOGO** — Large ASCII art logo in red
4. **Boot messages** — Anti-forensic module loading with hex addresses (`memory_scraper`, `process_hider`, `log_cleaner`, etc.)
5. **Tor handshake** — 3-hop relay status, exit node, circuit latency
6. **type_text()** — Animated "YOUR CONNECTION IS NOW ANONYMIZED" / "YOUR IDENTITY REMAINS HIDDEN"

### app/theme.py — Theme Engine

Four color presets:

| Theme     | Primary | Accent   | Background |
|-----------|---------|----------|------------|
| `matrix`  | Green   | Bright green | Black   |
| `amber`   | Yellow  | Bright yellow | Black   |
| `terminal`| Cyan    | White    | Black       |
| `hacker`  | Red     | Bright red | Dark red bg|

Persisted to `~/.tether/theme.json`.

### app/vfs.py — Virtual Filesystem

In-memory Linux-style filesystem with:

- `/proc/` — System info files (cpuinfo, meminfo, uptime, version, net/dev)
- `/etc/` — Configuration (hostname, resolv.conf, passwd, tether.conf)
- `/home/root/` — User home directory
- `/tmp/` — Temporary files
- Full path resolution, directory traversal, file ops

### app/session.py — Session Logging

- `log_cmd(cmd, output)` — Appends to `~/.tether/session.log` with timestamps
- `view_log(n)` — Returns last N lines of the session log

## Command Modules

Located in `app/commands/`:

| Module        | Commands                                         |
|---------------|--------------------------------------------------|
| `recon.py`    | nmap, dnsrecon, gobuster, theharvester, whatweb, whois, enum4linux, cewl |
| `exploit.py`  | searchsploit, hydra, hash-identifier             |
| `anon.py`     | proxychains, macchanger, anonsurf                |
| `scan.py`     | nikto (web vuln scanner), nuclei (template scanner)|
| `web.py`      | wpscan (WordPress enumeration + vuln DB)         |
| `forensics.py`| binwalk, hexdump, strings, exiftool              |
| `cron.py`     | CronDaemon (list/add/del/start/stop/status)      |
| `wireless.py` | iwconfig, airmon-ng, airodump-ng (via netsh)    |

Each module exports a `register(commands, aliases)` function called by
`register_all()` in `register.py` during shell initialization.

## Kernel Layer

### kernel/torctl.py

Communicates with Tor's control port (127.0.0.1:9051). Sends `SIGNAL NEWNYM`
to request a new circuit (new exit node IP). Uses raw sockets — no external
dependencies. Authenticates via `AUTHENTICATE` with empty string (default
Tor cookie auth is supported).

### kernel/probe.py

Queries external services (ipify.org, icanhazip.com, ifconfig.me, api.ipify.org)
through the Tor SOCKS5 proxy to verify current public IP. Falls through multiple
services for reliability. Timeout: 10 seconds per service.

### kernel/rotator.py

Orchestrator combining torctl + probe into a single `rotate()` call.
Flow:
1. `probe.get_current_ip()` — record old IP
2. `torctl.newnym()` — SIGNAL NEWNYM
3. Wait 3 seconds for circuit switch
4. `probe.get_current_ip()` — record new IP
5. Compare: if different, success
6. Returns dict: `{success, old_ip, new_ip, rotations}`

### kernel/scheduler.py

Background threading-based scheduler. Calls `rotator.rotate()` every N seconds
(default 60). Logs each rotation with timestamp. Daemon mode runs in background
process. Can be stopped via `stop_daemon()` or PID file.

## Data Flow

```
User launches tether
        |
   boot_sequence()
        |
   splash_screen() -> matrix_rain() -> logo -> boot msgs
        |
   shell.start()
        |
   REPL loop:
     readline("> ")
     _execute(command):
       parse pipe/redirect
       dispatch to command module or built-in
       capture output
       write to redirect file if needed
       return output to user
        |
   On exit:
     stop scheduler (if running)
     show_cursor()
```

## Configuration

System configuration: `etc/tether.conf`

```
[rotation]
interval = 60

[tor]
host = 127.0.0.1
control_port = 9051
socks_port = 9050
```

## Security Model

- All traffic routes through Tor SOCKS5 proxy (127.0.0.1:9050)
- DNS lookups go through Tor (SOCKS5 resolves remotely)
- Kill switch blocks non-Tor traffic
- Multiple fallback IP verification services
- No persistent logs of IP history by default

## Cross-Platform Support

| Feature            | Linux | macOS | Windows |
|--------------------|-------|-------|---------|
| Tor control port   | yes   | yes   | yes     |
| SOCKS5 proxy       | yes   | yes   | yes     |
| Shell (REPL)       | yes   | yes   | yes     |
| Daemon mode        | yes   | yes   | yes     |
| Wireless (netsh)   | —     | —     | yes     |
| Installer          | .sh   | .sh   | .ps1    |

## Dependencies

- **Python 3.7+** — core runtime
- **Tor daemon** — provides the anonymization network
- **PySocks** — SOCKS5 proxy support for urllib
- **Rich** — terminal formatting (optional, fallback to ANSI)

## Test Coverage

76 tests across all subsystems:

- `test_torctl.py` — Tor control protocol, NEWNYM signal
- `test_probe.py` — IP verification through proxy
- `test_rotator.py` — Rotation orchestrator
- `test_scheduler.py` — Background timer
- `test_network.py` — Network helpers
- `test_pidfile.py` — PID file management
- `test_cli.py` — CLI argument parsing
- `test_commands_recon.py` — 12 tests for recon module
- `test_commands_exploit.py` — 15 tests for exploit module
- `test_commands_anon.py` — 11 tests for anon module
