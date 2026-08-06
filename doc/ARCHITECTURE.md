# Tether OS Architecture

**Version:** 1.1.2

**Author:** Trapzzy  
**Design Philosophy:** Unix-inspired — do one thing well, compose via pipes. Bootable from ISO, fits entirely in RAM.

## Overview

Tether OS has two distinct layers:

1. **Operating System** — Buildroot-based Linux distribution with Busybox, Tor, iptables, Python 3, booting from a 27MB ISOLINUX ISO into initramfs (entirely RAM-based).
2. **Application Shell** — Pure Python 3.7+ REPL shell with 90+ pentesting commands, Tor IP rotation engine, virtual filesystem, theme engine, and session management.

---

## Operating System Layer

### Boot Sequence

```
Power-on
  |
SeaBIOS
  |
ISOLINUX (from ISO)
  |  Loads bzImage + rootfs.cpio.gz
  |  Kernel cmdline: console=ttyS0 net.ifnames=0
  v
Linux Kernel 6.1.44
  |  Unpacks initramfs (rootfs.cpio.gz) into tmpfs
  |  Runs /init (custom PID 1 shell script)
  v
/init (PID 1)
  |  mount -t proc /proc
  |  /etc/init.d/rcS (delegates boot scripts)
  v
rcS (runs via /init, not Busybox init)
  |  mount -t sysfs, tmpfs, devpts
  |  mdev -s (populate /dev)
  |  ip link set lo up
  |  dmesg -n 1
  |
  |  for i in /etc/init.d/S*; do $i start; done
  |    S01iptables: Firewall kill switch
  |      fail-closed DROP policy; only the Tor service account may egress
  |    S02network: DHCP on eth0
  |      ip link set eth0 up; udhcpc -i eth0 -q -n
  |    S03tor: Tor daemon
  |      tor -f /etc/tor/torrc &
  |      SOCKS5 proxy on :9050
  |      Control port on :9051
  v
/init continues
  |  Launches /usr/bin/tether
  |    sets the installed application path and calls app.entrypoint
  v
Tether OS Shell (REPL)

If the shell exits (crash or user exit), /init respawns it in a
while loop. If /usr/bin/tether is missing, a rescue /bin/sh
is provided with the message "Rescue shell (exit to restart)."
```

### Init Scripts

| Script | Order | Function |
|--------|-------|----------|
| `S01iptables` | 1 | Block all non-Tor traffic |
| `S02network` | 2 | DHCP on eth0 |
| `S03tor` | 3 | Tor daemon (SOCKS5 + Control) |

### Kernel Configuration

Fragment at `board/tether/kernel.config`:

```
CONFIG_BLK_DEV_INITRD=y       # Initramfs support
CONFIG_E1000=y                # Intel PRO/1000 NIC
CONFIG_E1000E=y               # Intel PRO/1000 PCIe NIC
CONFIG_NETFILTER=y            # Firewall subsystem
CONFIG_IP_NF_IPTABLES=y       # iptables
CONFIG_NF_CONNTRACK=y         # Connection tracking
CONFIG_NF_NAT=y               # NAT support
CONFIG_IP_NF_NAT=y            # IPv4 NAT
CONFIG_IP_NF_TARGET_MASQUERADE=y
CONFIG_NETFILTER_XT_MATCH_CONNTRACK=y
CONFIG_NETFILTER_XT_MATCH_STATE=y
CONFIG_NETFILTER_XT_MATCH_ADDRTYPE=y
```

### Buildroot External Tree

```
buildroot-external-tether/
  board/tether/
    rootfs_overlay/           # Files copied on top of default rootfs
      etc/inittab             # Busybox init config
      etc/init.d/rcS          # Boot sequence
      etc/init.d/S01iptables  # Kill switch
      etc/init.d/S02network   # DHCP
      etc/init.d/S03tor       # Tor daemon
      etc/tor/torrc           # Tor configuration
    kernel.config             # Kernel config fragment
    post-build.sh             # Post-build: trim tests and normalize permissions
    post-image.sh             # Post-image: build ISOLINUX ISO with xorriso
  configs/
    tether_os_defconfig       # Saved Buildroot .config
```

---

## Application Shell Layer

### Layer Architecture

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

### app/shell.py — Main REPL

The shell provides a Claude Code-inspired terminal interface with:

- **Scroll region layout** — Uses ANSI `DECSTBM` (`\033[<top>;<bottom>r`) to partition the terminal:
  - **Fixed header** (lines 1-6): TRAP HUB title bar, version, command hint, command count, separator
  - **Scrollable body** (lines 7 to h-2): Command output, scrolls independently via the ANSI scroll region
  - **Fixed footer** (line h-1): Input prompt (`> `) with inline editing
  - **Fixed status bar** (line h): Current IP, rotation count, Tor status, threat level, active theme
- **`>` prompt** — Clean, minimal prompt prefix at the fixed footer line
- **Pipe support** — `command1 | command2` chains commands via `_pipe_output()`
- **Redirect support** — `>` write, `>>` append to virtual filesystem paths
- **`.th` scripts** — Positional arg substitution (`$1`-`$N`, `$@`)
- **Session persistence** — `save`/`restore` commands write/read JSON state
- **Command registry** — 90+ commands loaded from `app/commands/` modules
- **Tab completion** — Auto-completes commands and virtual filesystem paths
- **Command history** — In-memory history with up/down arrow navigation

### app/banner.py — Boot Sequence

Multi-stage animated boot:
1. **splash_screen()** — Dark screen, hacker frame, pulsing "TARGET ACQUIRED"
2. **matrix_rain()** — Green digital rain
3. **TRAP_HUB_LOGO** — ASCII art logo
4. **Boot messages** — Runtime component initialization
5. **Tor status** — Reports that the shell is ready for verification
6. **type_text()** — Directs the user to verify protected status

### app/theme.py — Theme Engine

| Theme     | Primary | Accent   | Background |
|-----------|---------|----------|------------|
| `matrix`  | Green   | Bright green | Black   |
| `amber`   | Yellow  | Bright yellow | Black   |
| `terminal`| Cyan    | White    | Black       |
| `hacker`  | Red     | Bright red | Dark red bg|

### app/vfs.py — Virtual Filesystem

In-memory Linux-style filesystem:
- `/proc/` — System info (cpuinfo, meminfo, uptime, net/dev)
- `/etc/` — Configuration (hostname, resolv.conf, passwd, tether.conf)
- `/home/root/` — User home directory
- `/tmp/` — Temporary files

### app/session.py — Session Logging

- `log_cmd(cmd, output)` — Appends to `~/.tether/session.log`
- `view_log(n)` — Returns last N lines

## Command Modules

Located in `app/commands/`:

| Module        | Commands                                         |
|---------------|--------------------------------------------------|
| `recon.py`    | nmap, dnsrecon, gobuster, theharvester, whatweb, whois, enum4linux, cewl |
| `exploit.py`  | searchsploit, hydra, hash-identifier             |
| `anon.py`     | proxychains, macchanger, anonsurf                |
| `scan.py`     | nikto, nuclei                                    |
| `web.py`      | wpscan                                           |
| `forensics.py`| binwalk, hexdump, strings, exiftool              |
| `cron.py`     | CronDaemon (list/add/del/start/stop/status)      |
| `wireless.py` | iwconfig, airmon-ng, airodump-ng                |

## Kernel Layer

### kernel/torctl.py

Communicates with Tor control port (127.0.0.1:9051). Sends `SIGNAL NEWNYM`
to request a new circuit. Uses raw sockets — no external dependencies.

### kernel/probe.py

Queries external services (ipify.org, icanhazip.com, ifconfig.me, api.ipify.org)
through Tor SOCKS5 proxy to verify current public IP. Multiple fallbacks.

### kernel/rotator.py

Orchestrator combining torctl + probe:
1. `probe.get_current_ip()` — record the verified old Tor egress IP
2. `torctl.newnym()` — SIGNAL NEWNYM
3. Poll within a bounded timeout
4. `probe.get_current_ip()` — record the verified new Tor egress IP
5. Report success only when the egress address changes

### kernel/scheduler.py

Background threading scheduler. Calls `rotator.rotate()` every N seconds
(default 60). Logs each rotation. Daemon mode runs in background process.

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

- Application network commands use Tor SOCKS5 with remote DNS resolution.
- The boot image applies a fail-closed iptables policy and permits external traffic only for the Tor service account.
- Protected status requires both control-port authentication and a successful Tor egress verification.
- Multiple fallback IP verification services
- Boots entirely in RAM — no persistent storage

## Cross-Platform Support (App Only)

| Feature            | Linux | macOS | Windows |
|--------------------|-------|-------|---------|
| Tor control port   | yes   | yes   | yes     |
| SOCKS5 proxy       | yes   | yes   | yes     |
| Shell (REPL)       | yes   | yes   | yes     |
| Daemon mode        | yes   | yes   | yes     |
| Wireless (netsh)   | —     | —     | yes     |
| Installer          | .sh   | .sh   | .ps1    |

## Dependencies

- **Linux kernel 6.1.44** — boot platform (via Buildroot)
- **Busybox 1.36.1** — system utilities + init
- **Tor 0.4.8.11** — anonymization network
- **iptables 1.8.9** — kernel-level kill switch
- **Python 3.11** — runtime for the Tether app
- **PySocks** — SOCKS5 proxy support

## Test Coverage

96 tests cover the control layer, network adapters, command modules, shell parser and execution engine, virtual filesystem, configuration, and Buildroot integration contracts.
