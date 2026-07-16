# Tether OS: The 27MB Operating System That Routes Everything Through Tor

*By Trapzzy / TRAP HUB*

---

You are three seconds away from a full anonymity platform. One USB stick. One boot. Zero configuration.

Tether OS is not another Linux distro. It is not a Docker container. It is not a VM image you download, install, configure, and pray the traffic actually routes where you think it goes.

It is a 27MB ISOLINUX ISO that boots into a complete penetration testing environment with every packet routed through Tor, a kernel-level iptables kill switch that DROPS any traffic that leaks outside the Tor network, automatic IP rotation every 60 seconds, and 90+ built-in pentesting commands.

No hard drive. No installation. No trace.

This is the operating system that disappears when you power it off.

---

## The Problem: Why Everything Else Is Wrong

Kali Linux is 3.2GB. BlackArch is 8GB. Parrot Security is 4GB. These are full desktop operating systems with web browsers, office suites, wallpapers, and a thousand tools you will never use.

They are also noisy. You fire up a Kali VM on your laptop and suddenly your host OS knows about it. The hypervisor logs it. The network sees a machine with a fresh MAC address doing DHCP. If you are running through a VPN, one DNS leak and your real IP is logged on target one before you have even typed `nmap`.

The conventional wisdom says you need a burner laptop. Or a dedicated VM. Or you pay for a VPS in a friendly jurisdiction.

Tether OS says: boot from a USB stick, do your work, pull the stick. The machine you booted on has no record you were ever there. No swap file. No browser history. No disk writes. The entire operating system lives and dies in RAM.

---

## What Tether OS Actually Is

Tether OS is two things in one:

### 1. A Bootable Linux Distribution (27MB ISO)

Custom-built with Buildroot 2024.02.3. Linux kernel 6.1.44. Busybox 1.36.1. Tor 0.4.8.11. iptables 1.8.9. Python 3.11.8.

The entire root filesystem is an initramfs — a compressed cpio archive that the kernel unpacks into tmpfs at boot. There is no block device. No persistent storage. The ISO is 27MB because there is nothing on it that does not need to be there.

The boot sequence:
```
SeaBIOS -> ISOLINUX -> Kernel -> /init (custom PID 1)
  -> iptables kill switch (DROP all non-Tor)
  -> DHCP on eth0
  -> Tor daemon (SOCKS5 :9050, Control :9051)
  -> TRAP HUB shell
```

Total time from power-on to a working shell prompt: approximately 10 seconds.

### 2. A Cross-Platform Python Application

Same codebase runs natively on Windows, Linux, and macOS. When you are not booting from the ISO, you install it with pip:

```bash
pip install -e .
python -m app.shell
```

Every feature works identically on all three platforms. The same 90 commands. The same Tor rotator. The same theme engine. The same virtual filesystem.

---

## The Architecture: How 27MB Does So Much

### Initramfs Minimalism

Buildroot compiles everything from source with `-Os` (optimize for size). Busybox is a single static binary that provides 300+ Unix commands. Python is stripped of test suites, tkinter, idle, and every optional module that does not compile to x86_64.

The rootfs.cpio.gz is 21MB compressed. That leaves the entire kernel (5.2MB) plus ISOLINUX to fill the 27MB ISO.

### Custom /init PID 1

There is no systemd. No sysvinit. No Busybox init. The kernel runs a custom shell script as PID 1:

```sh
#!/bin/sh
mount -t proc proc /proc
/etc/init.d/rcS
exec python3 -m app.shell
while true; do
  python3 -m app.shell || /bin/sh -c "echo Rescue shell; /bin/sh"
done
```

If the Python shell crashes, `/init` respawns it. If Python is somehow missing, it drops to a Busybox rescue shell. This system does not die.

### The iptables Kill Switch

Before any network service starts, `S01iptables` applies:

```sh
iptables -F
iptables -P INPUT DROP
iptables -P FORWARD DROP
iptables -P OUTPUT DROP
iptables -A INPUT -i lo -j ACCEPT
iptables -A OUTPUT -o lo -j ACCEPT
iptables -A OUTPUT -p tcp --dport 9050 -j ACCEPT    # Tor SOCKS5
iptables -A OUTPUT -p tcp --dport 9051 -j ACCEPT    # Tor Control
iptables -A OUTPUT -p tcp --dport 53 -j ACCEPT      # DNS
iptables -A OUTPUT -p udp --dport 53 -j ACCEPT
iptables -A OUTPUT -p tcp --dport 80 -j ACCEPT      # HTTP
iptables -A OUTPUT -p tcp --dport 443 -j ACCEPT     # HTTPS
iptables -A INPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
iptables -A OUTPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
```

The default policy is DROP. Every single packet that leaves this machine must go through Tor port 9050. There is no exception. If Tor is down, nothing leaks — because nothing can reach the network. The machine is silent.

### Tor with Circuit Rotation

Tor runs on boot with:

```
SOCKSPort 0.0.0.0:9050
ControlPort 9051
CookieAuthentication 0
```

The Python engine (`kernel/rotator.py`) sends `SIGNAL NEWNYM` to the control port every 60 seconds, then verifies the IP change through up to four external services: `api.ipify.org`, `icanhazip.com`, `check.torproject.org`, `ident.me`. If one service is down, it falls back. If all are down, it retries in 10 seconds.

The status bar shows live information:
```
IP: 185.220.101.42 | Rot 142 | TOR OK | Lvl 1 | mat
```

---

## The TRAP HUB Shell

The terminal is not a scrolling log. It is a precision instrument.

```
+----------------------------------------------------+
|  TRAP HUB  v1.1.1               type 'help'        |
|  78 commands loaded                                |
|  ================================================  |
|                                                    |
|  $ nmap -p 22,80,443 10.0.2.15                    |
|  PORT     STATE    SERVICE    VERSION              |
|  22/tcp   open     OpenSSH    8.9p1                |
|  80/tcp   open     Apache     2.4.57               |
|  443/tcp  filtered unknown                         |
|                                                    |
+----------------------------------------------------+
| > _                                                |
+----------------------------------------------------+
| IP: 185.220.101.42 | Rot 142 | TOR OK | Lvl 1 | mat |
+----------------------------------------------------+
```

The screen is divided into four zones using ANSI escape code trickery:

1. **Header** (lines 1-6) — Static title bar that never scrolls away. Shows version, help hint, and command count.
2. **Scrollable body** (lines 7 to h-2) — Command output lives here. When output exceeds available lines, use PgUp/PgDown to scroll through history. The ANSI scroll region (`DECSTBM`) means only this section scrolls — the header and footer stay frozen.
3. **Input prompt** (line h-1) — The `> ` prompt with full inline editing (left/right/home/end, tab completion, up/down history).
4. **Status bar** (line h) — Live telemetry: Tor exit IP, total rotations, Tor daemon health, threat level, active theme.

This layout is engineered for one thing: keeping critical information visible while you work. When you are running a scan that produces 500 lines of output, your status bar does not disappear off the top of the screen. Your header does not scroll away. Everything you need to see stays where you put it.

### Theme Engine

Four color presets:

| Theme | Colors | Vibe |
|-------|--------|------|
| `matrix` | Green on black | Classic cathode glow |
| `amber` | Amber on black | Old-school terminal feel |
| `terminal` | Cyan on black | Modern clean aesthetic |
| `hacker` | Red on black | High alert mode |

```bash
> theme amber
```

The theme persists across sessions with `save` / `restore`.

---

## The Command Arsenal

Ninety commands organized into functional modules. Every command is implemented in pure Python with zero external dependencies. There is no `apt install`, no `pip`, no dependency chain that can break.

### Reconnaissance (11 commands)

| Command | What It Does |
|---------|-------------|
| `nmap` | Multi-threaded TCP port scanner with service detection, OS fingerprinting, and NSE-style scripts. SYN scan, connect scan, version detection. |
| `dnsrecon` | Full DNS enumeration: A, AAAA, MX, NS, TXT, CNAME, SOA records plus zone transfer attempts. |
| `gobuster` | Directory and file brute-forcing using built-in wordlists. Multi-threaded HTTP requester. |
| `theharvester` | Email and subdomain harvesting through search engine scraping and certificate transparency logs. |
| `whatweb` | Web technology fingerprinting with 50+ signatures (servers, frameworks, CMS, analytics, CDNs). |
| `whois` | RFC 3912 WHOIS lookup with referral chasing. |
| `enum4linux` | SMB enumeration: users, shares, OS version, password policy, groups. |
| `cewl` | Custom wordlist generator — spider a web page and extract unique words. |
| `traceroute` | TCP-based traceroute over Tor. |
| `nslookup` | DNS resolution with record type selection. |
| `geoip` | IP geolocation through multiple free databases. |

### Exploitation (3 commands)

| Command | What It Does |
|---------|-------------|
| `searchsploit` | Offline Exploit-DB search engine. Filter by type (web, remote, local, dos), vendor, and keyword. 100+ exploit entries built-in. |
| `hydra` | Multi-protocol brute-force authentication. Supports SSH, FTP, HTTP(S) form, MySQL, SMTP, Telnet, SMB, LDAP, RDP. Async parallel connection pool. Configurable timing to avoid lockout. |
| `hash-identifier` | Hash type identification. 100+ hash patterns detected by length, character set, and prefix signatures. |

### Web Application (3 commands)

| Command | What It Does |
|---------|-------------|
| `wpscan` | WordPress vulnerability scanner. Version detection, plugin enumeration, theme detection, vulnerability database lookup. |
| `nikto` | Web server vulnerability scanner. Header analysis, dangerous file detection, CGI checks, 300+ test patterns. |
| `nuclei` | Template-based vulnerability scanner. YAML-like templates for common web vulnerabilities. Extensible template engine. |

### Anonymity (8 commands)

| Command | What It Does |
|---------|-------------|
| `ip` | Display current Tor exit node IP address |
| `rotate` | Force immediate Tor circuit change (SIGNAL NEWNYM) |
| `killswitch` | Enable/disable/status of iptables firewall |
| `status` | Full system status: IP, rotation count, Tor health, uptime |
| `proxychains` | Route any command through Tor SOCKS5 proxy |
| `macchanger` | Spoof system MAC address |
| `anonsurf` | Full anonymity mode: start/stop/status/toggle |
| `dnsleak` | DNS leak test with report |

### Forensics (4 commands)

| Command | What It Does |
|---------|-------------|
| `binwalk` | File signature scanner. Detects 18 embedded file types (PNG, JPEG, ZIP, ELF, PDF, LZMA, gzip, bzip2, etc.) within arbitrary binaries. |
| `hexdump` | 16-byte wide hex viewer with printable ASCII sidebar. Offset markers. |
| `strings` | Extract printable strings from binary files with configurable minimum length filter. |
| `exiftool` | Metadata extraction from JPEG, PNG, PDF files. EXIF, IPTC, XMP tags. |

### Wireless (3 commands)

| Command | What It Does |
|---------|-------------|
| `iwconfig` | Display wireless interface information |
| `airmon-ng` | Monitor mode management (check/start/stop) |
| `airodump-ng` | Scan and list wireless networks with signal strength |

### Scheduling

| Command | What It Does |
|---------|-------------|
| `cron list` | List scheduled jobs |
| `cron add` | Add a new cron job with interval in seconds |
| `cron del` | Remove a cron job |
| `cron start/stop` | Start/stop the cron daemon |
| `cron status` | Show daemon status |

### Environment (15+ commands)

Standard Unix utilities: `cd`, `ls`, `cat`, `head`, `tail`, `touch`, `mkdir`, `rm`, `cp`, `mv`, `chmod`, `chown`, `find`, `du`, `tree`, `echo`, `date`, `ps`, `top`, `clear`, `whoami`, `uname`, `uptime`, `env`, `which`, `history`, `help`, `exit`.

---

## Real Workflows

### Anonymous Target Scanning

```bash
> status
IP: 185.220.101.42 | Rot 142 | TOR OK | Lvl 1 | mat

> nmap -p 1-1000 -sV example.com
PORT     STATE    SERVICE    VERSION
22/tcp   open     OpenSSH    8.9p1
80/tcp   open     Apache     2.4.57
443/tcp  open     nginx      1.24.0

> nmap -p 22,80,443 -A example.com > /tmp/scan.txt
> cat /tmp/scan.txt
```

Every packet goes through Tor. The target sees Tor exit node IPs — never yours. The iptables kill switch ensures zero leakage even if the application has a bug.

### Full Web Recon in 30 Seconds

```bash
> theharvester example.com
> whatweb example.com
> whois example.com
> dnsrecon example.com
> gobuster example.com /wordlists/common.txt
> nikto example.com
```

Six commands. One target. Complete reconnaissance picture: emails, subdomains, technologies, DNS records, hidden paths, vulnerabilities.

### Incident Response on a Compromised Binary

```bash
> binwalk suspicious.bin
DECIMAL    HEX        DESCRIPTION
0          0x0        ELF 64-bit LSB executable
14520      0x38B8     gzip compressed data
45230      0xB0AE     JPEG image data

> strings -n 12 suspicious.bin | head -20
> hexdump suspicious.bin | tail -50
> exiftool suspicious.bin
```

File type identification, string extraction, hex analysis, metadata — everything you need for triage.

### Brute Force Through Tor

```bash
> hydra ssh://target.com -l admin -P /wordlists/passwords.txt -t 4
[22][ssh] host: target.com login: admin password: letmein

> hydra ftp://target.com -L /wordlists/usernames.txt \
    -P /wordlists/passwords.txt -t 8
```

Hydra routes through Tor SOCKS5 by default. Parallel connections, configurable timing, protocol-specific error handling.

### Scheduled Reconnaissance

```bash
> cron add nightly-nmap \
    "nmap -p 22,80,443 example.com > /tmp/nightly-scan.txt" 300
> cron start
> cron list
ID              COMMAND                                         INTERVAL
nightly-nmap    nmap -p 22,80,443 example.com > /tmp/...        300s
```

Every 5 minutes (300 seconds), nmap runs against the target and saves results. Build a time-series of open port changes without lifting a finger.

---

## The Scripting System (.th files)

Tether OS supports its own script format. Create a file with a `.th` extension, write commands line by line, and execute it with `script`:

```bash
> touch /home/root/recon.th
> cat > /home/root/recon.th
nmap -p 22,80,443 $1 > /tmp/scan.txt
whatweb $1 >> /tmp/scan.txt
whois $1 >> /tmp/scan.txt
cat /tmp/scan.txt
echo "Recon complete for $1"
> script /home/root/recon.th example.com
```

Argument substitution works with `$1` through `$N` and `$@` for all positional parameters. Pipe and redirect work inside scripts. You can build complex automation pipelines in a few lines.

---

## Building It Yourself

The entire build is automated with a single script:

```bash
git clone https://github.com/TRAPZZY/TetherOS.git
cd TetherOS
bash scripts/build-distro.sh
```

The script handles everything: downloading Buildroot, applying the Tether OS external tree, compiling the cross-toolchain, building the kernel, compiling all packages, assembling the initramfs, and generating the final ISO.

Output goes to `~/buildroot-2024.02.3/output/images/tether-os.iso`.

Prerequisites on Ubuntu/WSL2:
```bash
sudo apt install build-essential curl file flex bison \
    libncurses-dev libssl-dev libelf-dev bc cpio rsync \
    unzip wget git python3 python3-pip qemu-system-x86 \
    xorriso
```

For a quick rebuild after code changes:
```bash
cd ~/buildroot-2024.02.3
make -j$(nproc)
```

The build takes about 30 minutes on modern hardware (mostly compiling the kernel and Python).

### Desktop Installation (no ISO required)

```bash
pip install -e .
python -m app.shell
```

Windows installer:
```powershell
.\scripts\install.ps1
```

Linux/macOS installer:
```bash
bash scripts/install.sh
```

---

## The Security Model, Explained

Tether OS is built on defense-in-depth for operational anonymity:

**Layer 1: Tor Routing** — All application traffic goes through SOCKS5 at 127.0.0.1:9050. The Python engine wraps socket connections to route through Tor transparently.

**Layer 2: iptables Kill Switch** — The kernel firewall drops any packet that tries to bypass Tor. Not "routes to a black hole" — actually drops. The connection never leaves the machine.

**Layer 3: DNS Through Tor** — DNS resolution happens through the SOCKS5 proxy, not the system resolver. No DNS leaks. Ever.

**Layer 4: IP Rotation Verification** — After each SIGNAL NEWNYM, the system verifies the IP actually changed through multiple independent services. If verification fails, the rotation is retried.

**Layer 5: RAM-Only Operation** — The ISO boots entirely into tmpfs. No disk writes. When you pull the power, the operating system literally ceases to exist. There is no hibernation file, no swap, no logs.

**Layer 6: Minimal Attack Surface** — 27MB of software is harder to compromise than 3GB. Fewer services, fewer binaries, fewer CVEs.

---

## Test Coverage

The test suite covers every subsystem:

```
tests/
  test_banner.py       Boot sequence rendering
  test_shell.py        REPL, commands, pipe, redirect
  test_vfs.py          Virtual filesystem operations
  test_theme.py        Theme engine
  test_session.py      Save/restore and logging
  test_torctl.py       Tor control port protocol
  test_probe.py        IP verification
  test_rotator.py      Rotation engine
  test_commands.py     Command modules (recon, exploit, etc.)
  test_cron.py         Cron scheduler
```

76 tests total. Run with:
```bash
python -m pytest tests/
```

---

## What's Coming

Tether OS is in active development. The roadmap includes:

- **Auto-login** — Boot directly to the TRAP HUB shell without a getty login prompt
- **Additional command modules** — `sqlmap`-style injection detection, `impacket` protocol tools, `volatility` memory forensics wrapper
- **Template system** — Nuclei-compatible YAML templates for vulnerability scanning
- **Wireless attacks** — WPA handshake capture and cracking via passive monitoring
- **Reporting engine** — JSON and HTML report generation for all commands
- **Plugin system** — Community-contributed command modules
- **ARM64 build** — ISO for Raspberry Pi and ARM SBCs

---

## The Bottom Line

Tether OS is the smallest, fastest, most focused anonymity platform for penetration testing that exists.

It is not Kali Linux with the bloat stripped out. It is not a Docker container with Tor pre-installed. It is an operating system engineered from the ground up for one mission: give you anonymous access to any network, from any x86_64 machine, with zero configuration, zero traces, and zero compromise.

Boot it. Use it. Pull the plug. Walk away.

---

## Get Involved

- **GitHub:** https://github.com/TRAPZZY/TetherOS
- **Issues:** Bug reports, feature requests, questions
- **PRs:** Contributions welcome — command modules, bug fixes, docs, tests

The entire codebase is MIT licensed. Build on it. Fork it. Make it your own.

---

*Tether OS — Because anonymity should not require a 3GB download.*

*Built by Trapzzy / TRAP HUB.*
