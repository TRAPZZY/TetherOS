# Tether OS

**Anonymous penetration testing shell with automatic Tor IP rotation.**  
Built by Trapzzy — product of TRAP HUB.

[![Python 3.7+](https://img.shields.io/badge/python-3.7%2B-blue.svg)]()
[![License](https://img.shields.io/badge/license-MIT-green.svg)]()
[![Platform](https://img.shields.io/badge/platform-Windows%20|%20Linux%20|%20macOS-lightgrey.svg)]()

Tether OS is a full-featured hacking shell that routes all traffic through Tor with automatic IP rotation, provides 90+ built-in pentesting and forensics commands, and features a Claude Code-inspired terminal interface with a bold hacker-themed splash screen.

---

## Features

- **Automatic Tor IP rotation** — Rotates your exit node every 60 seconds via `SIGNAL NEWNYM`, verified through multiple IP check services
- **90+ built-in commands** — Recon, exploitation, forensics, web scanning, wireless, cron, anonymity tools — all self-contained, no external binary dependencies
- **Virtual Linux filesystem** — Full `/proc`, `/etc`, `/home/root`, `/tmp` with `cd`, `ls`, `pwd`, `mkdir`, `touch`, `rm`, `cat`, `head`, `tail`, `cp`, `mv`, `find`, `tree`, `du`, `chmod`, `chown`
- **Claude Code-inspired terminal** — Dark background, centered hacker splash with pulsing skull and `TARGET ACQUIRED` warning, bottom status bar showing IP/rotations/Tor status/threat level, braille-dot loading spinner
- **Pipe and redirect** — `|` for pipe chaining, `>` and `>>` for output redirection to the virtual filesystem
- **`.th` script execution** — Run Tether OS script files with positional argument substitution (`$1`, `$2`, `$@`)
- **Session logging** — Automatic logging to `~/.tether/session.log`, viewable with `log` command
- **Session save/restore** — Persist and restore shell state (cwd, rotation count, threat level, theme, history) across sessions
- **Theme engine** — Four presets: `matrix`, `amber`, `terminal`, `hacker` — ANSI color schemes persisted to `~/.tether/theme.json`
- **Cron scheduler** — Built-in cron daemon with `list`, `add`, `del`, `start`, `stop`, `status` — persists to `~/.tether/cron.json`
- **Tor Expert Bundle** — Ships with embedded Tor daemon on Windows, auto-configures ports 9050/9051
- **Cross-platform** — Pure Python 3.7+, runs on Windows (native), Linux, macOS

---

## Quick Start

```bash
# Install
pip install -e .

# Start Tether OS shell
tether

# Or start the background daemon
tetherd
```

### First-time setup

On first run, Tether OS will attempt to detect or install the Tor daemon automatically. You can also install Tor manually:

- **Windows:** Download Tor Expert Bundle from https://www.torproject.org/download/tor/
- **Linux:** `apt install tor` or `pacman -S tor`
- **macOS:** `brew install tor`

---

## Commands Reference

### Shell built-ins

| Command     | Description                                    |
|-------------|------------------------------------------------|
| `cd`        | Change directory (virtual filesystem)          |
| `pwd`       | Print working directory                        |
| `ls`        | List directory contents                        |
| `cat`       | Concatenate and display files                  |
| `head`      | Display first lines of a file                  |
| `tail`      | Display last lines of a file                   |
| `touch`     | Create empty file                              |
| `mkdir`     | Create directory                               |
| `rm`        | Remove file or directory                       |
| `rmdir`     | Remove empty directory                         |
| `cp`        | Copy file or directory                         |
| `mv`        | Move file or directory                         |
| `chmod`     | Change file permissions (simulated)            |
| `chown`     | Change file owner (simulated)                  |
| `find`      | Search for files by name                       |
| `du`        | Estimate file space usage                      |
| `tree`      | Display directory tree                         |
| `vstat`     | Display virtual filesystem stats               |
| `whoami`    | Display current user                           |
| `uname`     | Display system information                     |
| `clear`     | Clear terminal screen                          |
| `echo`      | Display a line of text                         |
| `date`      | Display current date/time                      |
| `uptime`    | Display shell uptime                           |
| `hostname`  | Display system hostname                        |
| `env`       | Display environment variables                  |
| `which`     | Locate a command                               |
| `ps`        | Display process list (simulated)               |
| `top`       | Display real-time process monitor              |
| `history`   | Display command history                        |
| `help`      | Display help and command list                  |
| `exit`      | Exit the shell                                 |
| `sudo`      | Simulate privilege escalation                  |
| `su`        | Simulate user switch                           |
| `shutdown`  | Shut down the shell                            |
| `reboot`    | Restart the shell                              |
| `reset`     | Reset terminal state                           |
| `banner`    | Display boot banner                            |
| `theme`     | Change color theme (`matrix`, `amber`, etc.)   |
| `log`       | View session log                               |
| `script`    | Run a `.th` script file                        |
| `motd`      | Display message of the day                     |
| `save`      | Save shell state to disk                       |
| `restore`   | Restore shell state from disk                  |

### Network & Connectivity

| Command       | Description                                    |
|---------------|------------------------------------------------|
| `ip`          | Display current Tor exit node IP               |
| `ifconfig`    | Display network interface information          |
| `ping`        | Ping a host (via system ping)                  |
| `netstat`     | Display network connections                    |
| `curl`        | HTTP request utility                           |
| `traceroute`  | Trace route to host (via system traceroute)    |
| `nslookup`    | DNS lookup utility                             |
| `geoip`       | Geolocate an IP address                        |
| `dnsleak`     | Check for DNS leaks                            |
| `speedtest`   | Test connection speed                          |
| `rotate`      | Force a Tor IP rotation                        |
| `killswitch`  | Enable/disable Tor kill switch                 |
| `status`      | Display Tether OS status                       |

### Reconnaissance

| Command        | Description                                    |
|----------------|------------------------------------------------|
| `nmap`         | Port scanner (multi-threaded, service detection)|
| `dnsrecon`     | DNS enumeration (A, MX, NS, TXT, CNAME, SOA)   |
| `gobuster`     | Directory and file brute-forcing               |
| `theharvester` | Email and subdomain harvesting from search engines|
| `whatweb`      | Web technology fingerprinting (50+ signatures) |
| `whois`        | WHOIS lookup utility                           |
| `enum4linux`   | SMB enumeration (users, shares, OS detection)  |
| `cewl`         | Custom wordlist generator from web pages       |

### Exploitation

| Command          | Description                                    |
|------------------|------------------------------------------------|
| `searchsploit`   | Exploit search with type/vendor filtering      |
| `hydra`          | Multi-protocol brute-force authentication      |
| `hash-identifier`| Hash type identification (100+ hash patterns)  |

### Anonymity

| Command       | Description                                    |
|---------------|------------------------------------------------|
| `proxychains` | Route commands through Tor SOCKS5 proxy        |
| `macchanger`  | Spoof MAC address (Windows via registry)       |
| `anonsurf`    | Anonymity mode: start/stop/status/toggle       |

### Web Application

| Command       | Description                                    |
|---------------|------------------------------------------------|
| `wpscan`      | WordPress scanner (version detection, vuln DB, user/plugin enumeration)|
| `nikto`       | Web vulnerability scanner (header checks, path probing, severity scoring)|
| `nuclei`      | Template-based vulnerability scanner (4 built-in templates)|

### Forensics

| Command      | Description                                    |
|--------------|------------------------------------------------|
| `binwalk`    | File signature scanner (18 signatures, entropy estimation)|
| `hexdump`    | Hex viewer (16-byte wide, ASCII sidebar)       |
| `strings`    | Extract printable strings with min-length filter|
| `exiftool`   | File metadata extraction (JPEG, PNG, PDF)      |

### Wireless

| Command       | Description                                    |
|---------------|------------------------------------------------|
| `iwconfig`    | Display wireless interface information (via netsh)|
| `airmon-ng`   | Monitor mode management (check/start/stop)     |
| `airodump-ng` | Scan for wireless networks (SSID, signal, channel, auth)|

### Scheduling

| Command   | Description                                    |
|-----------|------------------------------------------------|
| `cron`    | Cron job manager (list/add/del/start/stop/status)|

---

## Architecture

```
+-------------------------------------------------------+
|                    TETHER OS SHELL                      |
|  +-----------+  +----------+  +--------------------+   |
|  | boot      |  | banner   |  | shell (REPL)       |   |
|  | sequence  |  | splash   |  | 90+ commands       |   |
|  |           |  | matrix   |  | pipe/redirect      |   |
|  |           |  | rain     |  | script execution   |   |
|  +-----------+  +----------+  +--------------------+   |
|                        |                               |
|  +-------------------------------------------------+  |
|  | COMMAND MODULES                                  |  |
|  | recon | exploit | anon | scan | web | forensics  |  |
|  | cron  | wireless                                 |  |
|  +-------------------------------------------------+  |
|                        |                               |
|  +-------------------------------------------------+  |
|  | KERNEL                                           |  |
|  | rotator | torctl | probe | scheduler              |  |
|  +-------------------------------------------------+  |
|                        |                               |
|  +-------------------------------------------------+  |
|  | TOR NETWORK  (SOCKS5 :9050 | Control :9051)     |  |
|  +-------------------------------------------------+  |
+-------------------------------------------------------+
```

### Key files

| Path                  | Purpose                                    |
|-----------------------|--------------------------------------------|
| `app/shell.py`        | Main REPL shell (Claude Code-style UI)     |
| `app/banner.py`       | Boot sequence, splash, matrix rain, spinner|
| `app/theme.py`        | Theme engine (4 presets, ANSI helpers)     |
| `app/session.py`      | Session logging and view                   |
| `app/vfs.py`          | Virtual Linux filesystem                   |
| `app/commands/`       | 8 command modules (recon, exploit, etc.)   |
| `kernel/rotator.py`   | Tor IP rotation orchestrator               |
| `kernel/torctl.py`    | Tor control port communication             |
| `kernel/probe.py`     | External IP verification                   |
| `kernel/scheduler.py` | Background rotation scheduler              |
| `scripts/install.ps1` | Windows installer                          |
| `scripts/install.sh`  | Linux/macOS installer                      |
| `wordlists/`          | Built-in passwords, usernames, subdomains  |

---

## Configuration

Tether OS uses `~/.tether/` as its data directory:

```
~/.tether/
  tor/              # Tor Expert Bundle (Windows)
  session.log       # Command session log
  session.json      # Saved shell state
  theme.json        # Theme preference
  cron.json         # Cron job definitions
```

System configuration file: `etc/tether.conf`

---

## Development

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run tests
python -m pytest tests/

# Run tests with coverage
python -m pytest tests/ --cov=app --cov=kernel --cov=lib
```

76 tests covering all major subsystems.

---

## License

MIT &copy; Trapzzy / TRAP HUB

---

*Built for educational and authorized security testing purposes only. The authors assume no liability for misuse.*
