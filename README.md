# Tether OS

**Tor-routed penetration testing distribution — bootable ISO with verified Tor identity rotation.**

Built by [Trapzzy](https://github.com/TRAPZZY) — product of TRAP HUB.

![Buildroot](https://img.shields.io/badge/buildroot-2025.02.16_LTS-green.svg)
![Linux](https://img.shields.io/badge/kernel-6.12.27-blue.svg)
![Tor](https://img.shields.io/badge/tor-0.4.8.11-purple.svg)
![Python](https://img.shields.io/badge/python-3.11-yellow.svg)
![License](https://img.shields.io/badge/license-MIT-red.svg)

Tether OS is a bootable Linux distribution whose application network tools use Tor, backed by a fail-closed boot-image firewall and verified circuit rotation. It provides 90+ built-in pentesting and forensics commands, boots from an initramfs-based ISO, and also runs as a cross-platform desktop application on Windows, Linux, and macOS.

---

## Table of Contents

- [Quick Start](#quick-start)
- [Features](#features)
- [Screenshots](#screenshots)
- [Architecture Overview](#architecture-overview)
- [Commands Reference](#commands-reference)
- [Building from Source](#building-from-source)
- [Desktop Installation](#desktop-installation)
- [Development](#development)
- [Security Model](#security-model)
- [Changelog](#changelog)
- [License](#license)

---

## Quick Start

### Run in QEMU (fastest)

Download the latest ISO from [Releases](https://github.com/TRAPZZY/TetherOS/releases), then:

```bash
qemu-system-x86_64 -cdrom tether-os.iso -m 512
```

On Windows with QEMU installed:

```powershell
& "C:\Program Files\qemu\qemu-system-x86_64w.exe" -cdrom tether-os.iso -m 512
```

At first boot, TetherOS asks you to create a password for the non-root
`tether` account. Every console then uses the standard login flow before it
can enter the TRAP HUB shell.

### Write to USB

```bash
sudo dd if=tether-os.iso of=/dev/sdX bs=4M status=progress
```

### Desktop App (cross-platform)

```bash
# Clone and install
git clone https://github.com/TRAPZZY/TetherOS.git
cd TetherOS
pip install -e .

# Run
tether

# Or directly
python -m app.entrypoint
```

---

## Features

### Tether Shell 2 release candidate

- **TRAP HUB Command Deck** — A live session view for route verification,
  managed jobs, lock readiness, risk level, and command discovery; use
  `deck` or `deck --json`.
- **Real authenticated sessions** — No root auto-login or unauthenticated
  rescue shell. The boot image creates a non-root operator password and uses
  `getty`/`login` for every console.
- **Kali-style session lock** — `lock` and inactivity timeout delegate to the
  operating system. TetherOS uses `vlock -a` on local consoles and forces
  serial sessions back through login.
- **Managed background jobs** — Append `&` to an external command, then use
  `jobs`, `jobs show`, `wait`, and `cancel`. Commands are launched without a
  host command shell and output is bounded.
- **Typed command contracts** — Commands have machine-readable metadata,
  exit codes, unique IDs, timing, and lifecycle events. Run `help --json` for
  the contract catalog.
- **Privacy-safe history and logs** — Password/token arguments are redacted;
  sensitive command output is omitted from persistent session logs.
- **Optional graphical edition** — `TETHER_EDITION=desktop` builds a Weston
  kiosk and GTK/PyGObject Command Deck. Core remains dependency-light and is
  the default.

See [the Shell 2 engineering plan](doc/SHELL_2_PLAN.md),
[secure-session design](doc/SECURE_SESSION.md),
[threat model](doc/THREAT_MODEL.md), and
[release acceptance checklist](doc/RELEASE_ACCEPTANCE.md).

### Core

- **Automatic Tor IP rotation** — Rotates exit node every 60 seconds via `SIGNAL NEWNYM`, verified through multiple IP check services
- **90+ built-in commands** — Recon, exploitation, forensics, web scanning, wireless, cron, anonymity tools — all self-contained
- **Bootable Linux ISO** — ISOLINUX live image with a Linux 6.12.27 kernel, booting entirely in RAM
- **iptables kill switch** — Fail-closed boot-image firewall that permits external traffic only for the Tor service account
- **Tor on boot** — Tor daemon auto-starts, SOCKS5 proxy on `:9050`, control port on `:9051`
- **Cross-platform** — Pure Python 3.7+, runs on Windows (native), Linux, macOS

### Shell

- **Claude Code-inspired terminal** — Dark background, animated hacker splash, matrix rain, fixed header with scrollable output area
- **Pipe and redirect** — `|` for command chaining, `>` and `>>` for output redirection
- **`.th` script execution** — Run Tether OS script files with `$1`-`$N` and `$@` positional argument substitution
- **Virtual Linux filesystem** — Full `/proc`, `/etc`, `/home/root`, `/tmp` with `cd`, `ls`, `pwd`, `mkdir`, `touch`, `rm`, `cat`, `head`, `tail`, `cp`, `mv`, `find`, `tree`, `du`, `chmod`, `chown`
- **Theme engine** — Four presets: `matrix` (green), `amber` (yellow), `terminal` (cyan), `hacker` (red)
- **Session logging** — Automatic logging to `~/.tether/session.log`
- **Session save/restore** — Persist and restore shell state across sessions
- **Cron scheduler** — Built-in cron daemon with list/add/del/start/stop/status operations

---

## Architecture Overview

```
+-------------------------------------------------------+
|                    TETHER OS SHELL                      |
|  +-----------+  +----------+  +--------------------+   |
|  | banner    |  | shell    |  | 90+ commands       |   |
|  | splash    |  | (REPL)   |  | pipe/redirect      |   |
|  | matrix    |  | scroll   |  | script exec        |   |
|  | rain      |  | region   |  | virtual fs         |   |
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
|                        |                               |
|  +-------------------------------------------------+  |
|  | OPERATING SYSTEM  (Buildroot Linux)              |  |
|  | Kernel 6.12.27 | BusyBox | iptables | Python 3   |  |
|  | Boot: ISOLINUX -> initramfs -> /init -> tether   |  |
|  +-------------------------------------------------+  |
+-------------------------------------------------------+
```

### Boot Sequence

```
SeaBIOS
  |
ISOLINUX (from ISO)
  |  Loads bzImage + rootfs.cpio.gz
  v
Linux Kernel 6.12.27
  |  Unpacks initramfs into tmpfs
  |  Runs /init (custom PID 1 script)
  v
/init (PID 1)
  |  mount -t proc /proc
  |  /etc/init.d/rcS (boot scripts)
  |    S01iptables: Fail-closed firewall (Tor service egress only)
  |    S02network: DHCP on eth0
  |    S03tor: Tor daemon (SOCKS5 :9050, Control :9051)
  |  Launches /usr/bin/tether (Python shell)
  v
Tether OS Shell (REPL)
```

### Key Files

| Path | Purpose |
|------|---------|
| `buildroot-external-tether/` | Buildroot external tree for ISO build |
| `app/shell.py` | Main REPL shell with scroll region UI |
| `app/banner.py` | Boot sequence: splash, matrix rain, spinner, logo |
| `app/theme.py` | Theme engine: 4 ANSI color presets |
| `app/vfs.py` | Virtual in-memory Linux filesystem |
| `app/session.py` | Session logging and state save/restore |
| `app/commands/` | 8 command modules (recon, exploit, anon, scan, web, forensics, cron, wireless) |
| `kernel/rotator.py` | Tor IP rotation: NEWNYM + multi-service verification |
| `kernel/torctl.py` | Tor control port communication |
| `kernel/probe.py` | External IP verification via Tor SOCKS5 |
| `kernel/scheduler.py` | Background rotation scheduler |
| `scripts/build-distro.sh` | Full Buildroot ISO build automation |
| `scripts/rebuild.sh` | Cached rebuild through the canonical image builder |
| `scripts/install.ps1` | Windows desktop installer |
| `scripts/install.sh` | Linux/macOS desktop installer |
| `wordlists/` | Built-in passwords, usernames, subdomains |

---

## Commands Reference

### Shell Built-ins

| Command | Description |
|---------|-------------|
| `cd` | Change directory (virtual filesystem) |
| `pwd` | Print working directory |
| `ls` | List directory contents |
| `cat` | Display file contents |
| `head` | Display first lines of a file |
| `tail` | Display last lines of a file |
| `touch` | Create empty file |
| `mkdir` | Create directory |
| `rm` | Remove file or directory |
| `rmdir` | Remove empty directory |
| `cp` | Copy file or directory |
| `mv` | Move file or directory |
| `chmod` | Change file permissions (simulated) |
| `chown` | Change file owner (simulated) |
| `find` | Search for files by name |
| `du` | Estimate file space usage |
| `tree` | Display directory tree |
| `vstat` | Display virtual filesystem stats |
| `whoami` | Display current user |
| `uname` | Display system information |
| `clear` | Clear terminal screen |
| `echo` | Display a line of text |
| `date` | Display current date/time |
| `uptime` | Display shell uptime |
| `hostname` | Display system hostname |
| `env` | Display environment variables |
| `which` | Locate a command |
| `ps` | Display process list (simulated) |
| `top` | Display real-time process monitor |
| `history` | Display command history |
| `help` | Display help and command list |
| `exit` | Exit the shell |
| `sudo` | Simulate privilege escalation |
| `su` | Simulate user switch |
| `shutdown` | Shut down the shell |
| `reboot` | Restart the shell |
| `reset` | Reset terminal state |
| `banner` | Display boot banner |
| `theme` | Change color theme (matrix, amber, terminal, hacker) |
| `log` | View session log |
| `script` | Run a `.th` script file |
| `motd` | Display message of the day |
| `save` | Save shell state to disk |
| `restore` | Restore shell state from disk |

### Network & Anonymity

| Command | Description |
|---------|-------------|
| `ip` | Display current Tor exit node IP |
| `ifconfig` | Display network interface information |
| `ping` | Ping a host (via system ping) |
| `netstat` | Display network connections |
| `curl` | HTTP request utility |
| `traceroute` | Trace route to host |
| `nslookup` | DNS lookup utility |
| `geoip` | Geolocate an IP address |
| `dnsleak` | Check for DNS leaks |
| `speedtest` | Test connection speed |
| `rotate` | Force a Tor IP rotation |
| `killswitch` | Enable/disable Tor kill switch |
| `status` | Display Tether OS status |
| `proxychains` | Route commands through Tor SOCKS5 proxy |
| `macchanger` | Spoof MAC address |
| `anonsurf` | Anonymity mode: start/stop/status/toggle |

### Reconnaissance

| Command | Description |
|---------|-------------|
| `nmap` | Multi-threaded port scanner with service detection |
| `dnsrecon` | DNS enumeration (A, MX, NS, TXT, CNAME, SOA) |
| `gobuster` | Directory and file brute-forcing |
| `theharvester` | Email and subdomain harvesting from search engines |
| `whatweb` | Web technology fingerprinting (50+ signatures) |
| `whois` | WHOIS lookup utility |
| `enum4linux` | SMB enumeration (users, shares, OS detection) |
| `cewl` | Custom wordlist generator from web pages |

### Exploitation

| Command | Description |
|---------|-------------|
| `searchsploit` | Exploit search with type/vendor filtering |
| `hydra` | Multi-protocol brute-force authentication |
| `hash-identifier` | Hash type identification (100+ hash patterns) |

### Web Application

| Command | Description |
|---------|-------------|
| `wpscan` | WordPress scanner (version detection, vuln DB) |
| `nikto` | Web vulnerability scanner (header checks, path probing) |
| `nuclei` | Template-based vulnerability scanner |

### Forensics

| Command | Description |
|---------|-------------|
| `binwalk` | File signature scanner (18 signatures) |
| `hexdump` | Hex viewer (16-byte wide, ASCII sidebar) |
| `strings` | Extract printable strings with min-length filter |
| `exiftool` | File metadata extraction (JPEG, PNG, PDF) |

### Wireless

| Command | Description |
|---------|-------------|
| `iwconfig` | Display wireless interface information |
| `airmon-ng` | Monitor mode management (check/start/stop) |
| `airodump-ng` | Scan for wireless networks |

### Scheduling

| Command | Description |
|---------|-------------|
| `cron` | Cron job manager (list/add/del/start/stop/status) |

---

## Building from Source

### Prerequisites (Ubuntu, Debian, or WSL2)

```bash
sudo apt install build-essential curl file flex bison \
    libncurses-dev libssl-dev libelf-dev bc cpio rsync \
    unzip wget git python3 python3-pip qemu-system-x86 \
    xorriso
```

### Full Build

```bash
# Clone
git clone https://github.com/TRAPZZY/TetherOS.git
cd TetherOS

# Run automated build script
bash scripts/build-distro.sh
```

The script downloads the checksum-pinned Buildroot 2025.02.16 LTS release,
configures it for TetherOS, compiles the kernel and all packages, and writes
`tether-os.iso` under `~/buildroot-2025.02.16/output/images/`.

Core edition (default):

```bash
bash scripts/build-distro.sh
```

Optional graphical feasibility edition:

```bash
TETHER_EDITION=desktop bash scripts/build-distro.sh
```

### Quick Rebuild (after code changes)

```bash
cd ~/buildroot-2025.02.16
make -j$(nproc)
```

### Output Artifacts

```
output/images/
  bzImage                              Linux 6.12.27 kernel
  rootfs.cpio.gz                       Buildroot-generated initramfs
  tether-os.iso                        Bootable ISOLINUX image
  tether-os-<edition>.sha256           Release digest manifest
  tether-os-<edition>.buildroot-info.json
  tether-os-<edition>.sbom.cdx.json    CycloneDX dependency inventory
```

---

## Desktop Installation

For running Tether OS as a desktop application (without the Linux ISO):

### Windows

```powershell
# Automated installer
.\scripts\install.ps1

# Or pip install
pip install -e .
python -m app.shell
```

### Linux / macOS

```bash
# Automated installer
bash scripts/install.sh

# Or pip install
pip install -e .
python -m app.shell
```

---

## Development

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run tests
python -m pytest tests/

# Run with coverage
python -m pytest tests/ --cov=app --cov=kernel --cov=lib
```

The complete regression suite covers the control layer, network adapters,
commands, shell engine, virtual filesystem, authentication/lock contracts,
graphical adapter, configuration, and Buildroot image gates.

---

## Security Model

- **Application traffic through Tor** — Shared SOCKS5 transport at 127.0.0.1:9050
- **Fail-closed boot firewall** — External traffic is restricted to the Tor service account
- **Remote DNS for application tools** — Hostnames are resolved through SOCKS5h
- **Verified status** — Protection is reported only after Tor control authentication and egress verification
- **Multiple IP verification** — Falls back across 4+ external services
- **No persistent storage** — Entire OS runs in RAM
- **Automatic IP rotation** — Circuit changes every 60 seconds by default

---

## Changelog

See [CHANGELOG.md](doc/CHANGELOG.md) for full version history.

---

## License

MIT &copy; Trapzzy / TRAP HUB

---

*Built for educational and authorized security testing purposes only. The authors assume no liability for misuse.*
