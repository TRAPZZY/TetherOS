# Tether OS User Guide

This guide covers everything you need to know to use Tether OS effectively.

---

## Table of Contents

- [Starting Up](#starting-up)
- [The Shell Interface](#the-shell-interface)
- [Command Reference](#command-reference)
- [Virtual Filesystem](#virtual-filesystem)
- [Pipes and Redirects](#pipes-and-redirects)
- [Scripting (.th files)](#scripting-th-files)
- [Theme System](#theme-system)
- [Session Management](#session-management)
- [Tor IP Rotation](#tor-ip-rotation)
- [Cron Scheduling](#cron-scheduling)
- [Common Workflows](#common-workflows)

---

## Starting Up

### From the Desktop App

```bash
python -m app.shell
```

Or if installed:

```bash
tether
```

### From the ISO (QEMU)

```bash
qemu-system-x86_64 -cdrom tether-os.iso -m 512
```

The boot sequence performs:

1. **SeaBIOS** initializes hardware
2. **ISOLINUX** loads kernel + initramfs
3. **Linux 6.1.44** boots into RAM
4. **Boot animation** plays (spinner + splash screen)
5. **Tor daemon** starts automatically
6. **iptables kill switch** engages
7. **Tether OS shell** opens automatically

---

## The Shell Interface

The terminal is divided into four zones:

```
+----------------------------------------------------+
|  TRAP HUB  v1.1.1               type 'help'        |  <- Header (fixed)
|  78 commands loaded                                |
|  ================================================  |
|                                                    |
|  $ ls                                              |  <- Scrollable output area
|  DIR  /proc                                        |
|  DIR  /home                                        |
|  DIR  /tmp                                         |
|  ...                                               |
|                                                    |
|                                                    |
+----------------------------------------------------+
| > _                                                |  <- Input prompt (fixed)
+----------------------------------------------------+
| IP: 51.75.144.12 | Rot 142 | TOR OK | Lvl 1 | mat |  <- Status bar (fixed)
+----------------------------------------------------+
```

- **Header** — Shows version, help hint, and command count. Never scrolls.
- **Scrollable body** — Command output appears here. Use **PgUp** / **PgDown** to scroll through output history.
- **Input prompt** — Type commands at the `> ` prompt. Supports **inline editing** (left/right/home/end) and **up/down history**.
- **Status bar** — Live status: current Tor exit IP, rotation count, Tor daemon health, threat level, active theme.

---

## Command Reference

### Navigation

| Command | Example | Description |
|---------|---------|-------------|
| `cd` | `cd /home/root` | Change directory |
| `pwd` | `pwd` | Print working directory |
| `ls` | `ls -la /tmp` | List directory contents (supports `-l`, `-a`, `-la`) |
| `tree` | `tree /etc` | Display directory tree |

### File Operations

| Command | Example | Description |
|---------|---------|-------------|
| `cat` | `cat /etc/hosts` | Display file contents |
| `head` | `head -5 file.txt` | First N lines (default 10) |
| `tail` | `tail -20 file.txt` | Last N lines (default 10) |
| `touch` | `touch /tmp/newfile` | Create empty file |
| `mkdir` | `mkdir /home/root/tools` | Create directory (supports `-p`) |
| `rm` | `rm -rf /tmp/dir` | Remove file or directory |
| `rmdir` | `rmdir /tmp/empty` | Remove empty directory |
| `cp` | `cp /tmp/a /tmp/b` | Copy file or directory |
| `mv` | `mv /tmp/a /tmp/b` | Move/rename file or directory |
| `chmod` | `chmod 755 /tmp/script.th` | Change permissions |
| `chown` | `chown root:root /tmp/file` | Change owner |
| `find` | `find /home -name "*.th"` | Search files by name |
| `du` | `du -sh /etc` | Estimate file space usage |

### System Info

| Command | Description |
|---------|-------------|
| `whoami` | Current user |
| `uname` | System information |
| `uptime` | Shell uptime |
| `hostname` | System hostname |
| `date` | Current date/time |
| `env` | Environment variables |
| `which` | Locate a command |
| `ps` | Process list (simulated) |
| `top` | Real-time process monitor |
| `history` | Command history |
| `vstat` | Virtual filesystem stats |

### Shell Control

| Command | Description |
|---------|-------------|
| `clear` | Clear terminal |
| `reset` | Reset terminal state |
| `banner` | Display boot banner |
| `help` | Show help and command list |
| `exit` | Exit the shell |
| `sudo` | Simulate privilege escalation |
| `su` | Simulate user switch |
| `shutdown` | Shut down the shell |
| `reboot` | Restart the shell |

### Network & Anonymity

| Command | Description |
|---------|-------------|
| `ip` | Current Tor exit node IP address |
| `ifconfig` | Network interface info |
| `ping` | Ping a remote host |
| `netstat` | Network connections |
| `curl` | HTTP request utility |
| `traceroute` | Trace route to host |
| `nslookup` | DNS lookup |
| `dnsleak` | DNS leak test |
| `geoip` | Geolocate an IP address |
| `speedtest` | Connection speed test |
| `rotate` | Force Tor IP rotation |
| `killswitch` | Tor kill switch on/off/status |
| `proxychains` | Route command through Tor |
| `macchanger` | Spoof MAC address |
| `anonsurf` | Full anonymity mode |

### Reconnaissance

| Command | Description |
|---------|-------------|
| `nmap` | Multi-threaded port scanner (TCP SYN, connect, service detection, OS detection) |
| `dnsrecon` | DNS enumeration (A, MX, NS, TXT, CNAME, SOA, zone transfer) |
| `gobuster` | Directory/file brute-forcer with wordlists |
| `theharvester` | Email/subdomain harvesting |
| `whatweb` | Web technology fingerprinting |
| `whois` | WHOIS lookup |
| `enum4linux` | SMB enumeration |
| `cewl` | Custom wordlist generator |

### Exploitation

| Command | Description |
|---------|-------------|
| `searchsploit` | Exploit database search (type, vendor, keyword filters) |
| `hydra` | Multi-protocol brute-force (SSH, FTP, HTTP, MySQL, SMTP, Telnet, SMB, LDAP, RDP) |
| `hash-identifier` | Hash type identification (100+ hash patterns) |

### Web Application

| Command | Description |
|---------|-------------|
| `wpscan` | WordPress scanner (version, plugins, themes, vulns) |
| `nikto` | Web vulnerability scanner |
| `nuclei` | Template-based vulnerability scanning |

### Forensics

| Command | Description |
|---------|-------------|
| `binwalk` | File signature scanning (18 signatures: PNG, ZIP, ELF, PDF, etc.) |
| `hexdump` | Hex viewer with ASCII sidebar |
| `strings` | Extract printable strings with min-length filter |
| `exiftool` | File metadata extraction (JPEG, PNG, PDF) |

### Wireless

| Command | Description |
|---------|-------------|
| `iwconfig` | Wireless interface info |
| `airmon-ng` | Monitor mode management |
| `airodump-ng` | Wireless network scanning |

### Scheduling

| Command | Description |
|---------|-------------|
| `cron list` | List cron jobs |
| `cron add JOB_ID "COMMAND" INTERVAL` | Add a cron job |
| `cron del JOB_ID` | Delete a cron job |
| `cron start` | Start cron daemon |
| `cron stop` | Stop cron daemon |
| `cron status` | Show cron daemon status |

---

## Virtual Filesystem

Tether OS provides a complete in-memory Linux filesystem:

| Path | Description |
|------|-------------|
| `/` | Root directory |
| `/home/` | User home directories |
| `/home/root/` | Root user home |
| `/etc/` | Configuration files (hosts, passwd, shadow, etc.) |
| `/tmp/` | Temporary files |
| `/proc/` | System process information |
| `/mnt/` | Mount point |

Default files are created at boot:
- `/etc/hostname` — "tether-os"
- `/etc/hosts` — Local host resolution
- `/etc/passwd` — User database
- `/etc/shadow` — Password hashes
- `/etc/resolv.conf` — DNS configuration
- `/home/root/.bashrc` — Shell aliases
- `/etc/fstab` — Filesystem table

---

## Pipes and Redirects

### Pipe (`|`)

Chain commands together:

```bash
> ls /home | head -3
> cat /etc/hosts | grep localhost
> ps | grep python
```

The left command's output becomes the right command's input.

### Redirect (`>` and `>>`)

Write output to a file:

```bash
> nmap 192.168.1.1 > /tmp/scan.txt
> echo "log entry" >> /tmp/log.txt
```

- `>` — Overwrite file
- `>>` — Append to file

---

## Scripting (.th files)

Tether OS supports running `.th` script files with argument substitution.

### Creating a Script

```bash
> touch /home/root/scan.th
> cat > /home/root/scan.th
nmap $1 > /tmp/scan-$2.txt
echo "Scan complete for $1"
```

### Running a Script

```bash
> script /home/root/scan.th 192.168.1.1 quick
```

This substitutes:
- `$1` → `192.168.1.1`
- `$2` → `quick`
- `$@` → `192.168.1.1 quick`

### Example Scripts

Port scan and geolocate:

```bash
nmap -p 22,80,443 $1 > /tmp/scan.txt
cat /tmp/scan.txt
geoip $1
```

Monitor IP rotation:

```bash
echo "Monitoring IP for $1 rotations..."
for i in $(seq 1 $1)
do
  ip
  sleep 60
done
```

---

## Theme System

Four built-in color themes:

| Theme | Colors | Apply |
|-------|--------|-------|
| `matrix` | Green on black | `theme matrix` |
| `amber` | Amber on black | `theme amber` |
| `terminal` | Cyan on black | `theme terminal` |
| `hacker` | Red on black | `theme hacker` |

Themes affect: prompt, status bar, command output, borders, headings, and all ANSI-colored elements.

Persist a theme by saving the session:

```bash
> theme amber
> save
```

---

## Session Management

### Saving State

```bash
> save
```

Persists to `~/.tether/session.save`:
- Current directory
- Command history
- Active theme
- Virtual filesystem state
- VFS stats

### Restoring State

```bash
> restore
```

### Session Logging

All commands and their output are automatically logged to `~/.tether/session.log`.

View the log:

```bash
> log
```

---

## Tor IP Rotation

### Automatic Rotation

By default, Tether OS rotates the Tor exit node every **60 seconds**. The rotator:

1. Sends `SIGNAL NEWNYM` to Tor control port (:9051)
2. Fetches external IP through Tor SOCKS5 (:9050)
3. Falls back across `api.ipify.org`, `icanhazip.com`, `check.torproject.org`, `ident.me`
4. Verifies the IP actually changed
5. Updates the status bar

### Manual Rotation

```bash
> rotate
```

### Monitoring

```bash
> status
> ip
```

The status bar shows: current IP, total rotations, Tor health, threat level.

---

## Common Workflows

### Anonymous Scanning

```bash
# Verify Tor is active
> status
> ip

# Scan target through Tor
> nmap -p 1-1000 example.com

# Log results
> nmap -p 22,80,443 example.com > /tmp/scan.txt
> cat /tmp/scan.txt
```

### Web Reconnaissance

```bash
# Gather intel
> theharvester example.com
> whatweb example.com
> whois example.com

# Brute-force directories
> gobuster example.com /wordlists/common.txt

# Scan for vulnerabilities
> nikto example.com
```

### Email Harvesting + Enumeration

```bash
> theharvester example.com
> dnsrecon example.com
> enum4linux example.com
```

### Password Auditing

```bash
# Generate custom wordlist
> cewl http://example.com

# Brute-force SSH
> hydra ssh://target.com -l admin -P /wordlists/passwords.txt
```

### Forensics Workflow

```bash
# Identify file type
> binwalk suspicious.bin

# Extract strings
> strings -n 10 suspicious.bin

# View hex dump
> hexdump suspicious.bin

# Check metadata
> exiftool suspicious.bin
```

### Scheduled Recon (Cron)

```bash
# Run nmap scan every 10 minutes
> cron add nightly-nmap "nmap -p 22,80,443 example.com > /tmp/nightly-scan.txt" 10

# Start cron daemon
> cron start

# Check jobs
> cron list
```

---

*Tether OS — Preparing for the future, underground.*
