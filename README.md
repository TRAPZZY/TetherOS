# Tether OS

**Anonymous penetration testing distribution — bootable ISO with automatic Tor IP rotation.**  
Built by Trapzzy — product of TRAP HUB.

[![Buildroot](https://img.shields.io/badge/buildroot-2024.02.3-green.svg)]()
[![Linux](https://img.shields.io/badge/kernel-6.1.44-blue.svg)]()
[![Tor](https://img.shields.io/badge/tor-0.4.8.11-purple.svg)]()
[![Python](https://img.shields.io/badge/python-3.11-yellow.svg)]()

Tether OS is a **bootable Linux distribution** that routes all traffic through Tor with automatic IP rotation, provides 90+ built-in pentesting and forensics commands, boots from a 27MB ISO, and fits entirely in RAM (initramfs-based).

---

## Quick Start

### Run in QEMU (fastest)

```bash
# Build (first time, ~15-30 min in WSL2)
cd ~/buildroot-2024.02.3
make -j$(nproc)

# Run
qemu-system-x86_64 -cdrom output/images/tether-os.iso -m 512
```

### Write to USB

```bash
sudo dd if=tether-os.iso of=/dev/sdX bs=4M status=progress
```

### Boot output

```
ISOLINUX -> kernel -> /init -> Busybox init -> rcS
-> iptables kill switch [OK]
-> DHCP (eth0) [OK]
-> Tor SOCKS5 :9050, Control :9051 [OK]
-> Login prompt on serial console [OK]
```

Login as `root` (no password).

---

## Build System

Tether OS is built with **Buildroot 2024.02.3** as an external tree.

### Prerequisites (Ubuntu/WSL2)

```bash
sudo apt install build-essential curl file flex bison \
    libncurses-dev libssl-dev libelf-dev bc cpio rsync \
    unzip wget git python3 python3-pip qemu-system-x86 \
    xorriso isolinux syslinux-common
```

### Build

```bash
git clone https://github.com/TRAPZZY/TetherOS.git
cd TetherOS

# Download and extract Buildroot
wget https://buildroot.org/downloads/buildroot-2024.02.3.tar.gz
tar xf buildroot-2024.02.3.tar.gz -C ~/
cd ~/buildroot-2024.02.3

# Configure and build
make qemu_x86_64_defconfig
# Then add BR2_EXTERNAL pointing to cloned repo
# Full script: TetherOS/scripts/build-distro.sh
make -j$(nproc)
```

### Output

```
output/images/
  bzImage          5.2M   Linux kernel 6.1.44
  rootfs.cpio.gz   21M    Initramfs (root filesystem)
  rootfs.ext2      500M   Ext2 rootfs image
  tether-os.iso    27M    Bootable ISO (ISOLINUX)
```

### Quick rebuild

```bash
cd ~/buildroot-2024.02.3
make -j$(nproc)
```

---

## External Tree Structure

```
buildroot-external-tether/
  board/tether/
    rootfs_overlay/          # Overrides Buildroot default rootfs
      etc/
        inittab              # Busybox init table
        init.d/
          rcS                # Boot sequence script
          S01iptables        # Firewall kill switch
          S02network         # DHCP on eth0
          S03tor             # Tor daemon
        tor/torrc            # Tor configuration
    kernel.config            # Kernel config fragment (initrd, e1000, netfilter)
    post-build.sh            # Deploys app code, installs pysocks, creates /init symlink
    post-image.sh            # Creates bootable ISOLINUX ISO with xorriso
  configs/
    tether_os_defconfig      # Saved Buildroot configuration
```

### Boot sequence

| Stage | Description |
|-------|-------------|
| ISOLINUX | Loads `bzImage` + `rootfs.cpio.gz` |
| Kernel | Unpacks initramfs, runs `/init` |
| Busybox init | Reads `/etc/inittab`, runs `rcS` |
| `rcS` | Mounts proc/sysfs/tmpfs, populates /dev, brings up lo |
| `S01iptables` | DROP all non-Tor traffic (kill switch) |
| `S02network` | DHCP on eth0 (e1000 driver) |
| `S03tor` | Tor daemon (SOCKS5 :9050, Control :9051) |
| Getty | Login prompt on serial console (ttyS0) |

### Kernel config additions

- `CONFIG_BLK_DEV_INITRD=y` — initramfs
- `CONFIG_E1000=y`, `CONFIG_E1000E=y` — NIC driver
- `CONFIG_NETFILTER=y`, `CONFIG_IP_NF_IPTABLES=y` — firewall
- `CONFIG_NF_CONNTRACK=y`, `CONFIG_NF_NAT=y` — connection tracking
- `CONFIG_NETFILTER_XT_MATCH_CONNTRACK`, `_STATE`, `_ADDRTYPE` — iptables matchers

---

## Features

- **Automatic Tor IP rotation** — Rotates exit node every 60 seconds via `SIGNAL NEWNYM`, verified through multiple IP check services
- **90+ built-in commands** — Recon, exploitation, forensics, web scanning, wireless, cron, anonymity tools — all self-contained
- **Virtual Linux filesystem** — Full `/proc`, `/etc`, `/home/root`, `/tmp` with `cd`, `ls`, `pwd`, `mkdir`, `touch`, `rm`, `cat`, `head`, `tail`, `cp`, `mv`, `find`, `tree`, `du`, `chmod`, `chown`
- **Claude Code-inspired terminal** — Dark background, hacker splash, bottom status bar
- **Pipe and redirect** — `|` for pipe chaining, `>` and `>>` for output redirection
- **`.th` script execution** — Run Tether OS script files with positional argument substitution
- **Session logging** — Automatic logging to `~/.tether/session.log`
- **Session save/restore** — Persist and restore shell state across sessions
- **Theme engine** — Four presets: `matrix`, `amber`, `terminal`, `hacker`
- **Cron scheduler** — Built-in cron daemon with CRUD operations
- **Cross-platform** — Pure Python 3.7+, runs on Windows (native), Linux, macOS

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
| `wpscan`      | WordPress scanner (version detection, vuln DB) |
| `nikto`       | Web vulnerability scanner (header checks, path probing)|
| `nuclei`      | Template-based vulnerability scanner           |

### Forensics

| Command      | Description                                    |
|--------------|------------------------------------------------|
| `binwalk`    | File signature scanner (18 signatures)         |
| `hexdump`    | Hex viewer (16-byte wide, ASCII sidebar)       |
| `strings`    | Extract printable strings with min-length filter|
| `exiftool`   | File metadata extraction (JPEG, PNG, PDF)      |

### Wireless

| Command       | Description                                    |
|---------------|------------------------------------------------|
| `iwconfig`    | Display wireless interface information         |
| `airmon-ng`   | Monitor mode management (check/start/stop)     |
| `airodump-ng` | Scan for wireless networks                     |

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
|                        |                               |
|  +-------------------------------------------------+  |
|  | OPERATING SYSTEM  (Buildroot Linux)              |  |
|  | Kernel 6.1.44 | Busybox | iptables | Python 3    |  |
|  | Boot: ISOLINUX -> initramfs -> Busybox init       |  |
|  +-------------------------------------------------+  |
+-------------------------------------------------------+
```

### Key files

| Path                  | Purpose                                    |
|-----------------------|--------------------------------------------|
| `buildroot-external-tether/` | Buildroot external tree                    |
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
| `scripts/build-distro.sh` | Full Buildroot build automation        |
| `wordlists/`          | Built-in passwords, usernames, subdomains  |

---

## Development

```bash
# Install development dependencies (for app testing)
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
