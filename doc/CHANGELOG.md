# Changelog

## v1.1.0 (2026-07-15)

### Buildroot Linux Distribution

- **Bootable ISO** — Full Linux distribution built with Buildroot 2024.02.3, boots from 27MB ISOLINUX ISO via QEMU or USB
- **Linux kernel 6.1.44** — Custom kernel config with initramfs, e1000 NIC driver, netfilter/NAT/connection tracking
- **Initramfs boot** — Kernel unpacks `rootfs.cpio.gz` into tmpfs, runs Busybox init, whole OS in RAM
- **Init scripts** — `rcS` → `S01iptables` (kill switch) → `S02network` (DHCP) → `S03tor` (Tor daemon) → getty login
- **iptables kill switch** — DROP all non-Tor traffic; allow loopback, Tor ports (443/9001/9030), DNS (53/udp), established connections
- **Busybox 1.36.1** — Statically compiled system utilities + init
- **Tor 0.4.8.11** — SOCKS5 proxy on :9050, Control port on :9051, auto-start on boot
- **Python 3.11.8** — Runtime for the Tether application shell
- **PySocks** — Installed in rootfs for SOCKS5 proxy support
- **Buildroot external tree** — `buildroot-external-tether/` with board config, rootfs overlay, kernel fragment, post-build/post-image scripts
- **Build automation** — `scripts/build-distro.sh` (full) and `scripts/rebuild.sh` (quick rebuild)
- **Cross-platform** — Build in WSL2 Ubuntu, run anywhere via QEMU or bare metal

## v1.0.0 (2026-07-14)

### Initial Release

- **Tor IP rotation engine** — Automatic 60-second rotation via `SIGNAL NEWNYM` with multi-service IP verification (ipify.org, icanhazip.com, ifconfig.me, api.ipify.org)
- **REPL shell** — Claude Code-inspired terminal with `>` prompt, bottom status bar, and dark background
- **90+ built-in commands** across 8 modules:
  - Recon: nmap, dnsrecon, gobuster, theharvester, whatweb, whois, enum4linux, cewl
  - Exploit: searchsploit, hydra, hash-identifier
  - Anonymity: proxychains, macchanger, anonsurf
  - Web scanning: nikto, nuclei, wpscan
  - Forensics: binwalk, hexdump, strings, exiftool
  - Wireless: iwconfig, airmon-ng, airodump-ng
  - Scheduling: cron (daemon with CRUD operations)
- **Boot sequence** — Multi-stage animated boot: hacker splash screen with skull art and pulsing "TARGET ACQUIRED" warning, matrix rain, TRAP HUB ASCII logo, anti-forensic module loading messages, Tor handshake verification
- **Virtual filesystem** — In-memory Linux-style VFS with /proc, /etc, /home/root, /tmp and full file operations
- **Pipe and redirect** — `command1 | command2` chaining, `>` write and `>>` append redirection
- **Theme engine** — 4 presets (matrix, amber, terminal, hacker) persisted to `~/.tether/theme.json`
- **Session persistence** — Session logging to `~/.tether/session.log`, state save/restore via JSON
- **Script execution** — `.th` script files with `$1`-`$N` and `$@` positional argument substitution
- **Tor Expert Bundle** — Embedded Tor daemon support for Windows
- **Cross-platform** — Windows, Linux, macOS via pure Python 3.7+
- **Installer scripts** — `scripts/install.ps1` (Windows) and `scripts/install.sh` (Linux/macOS)
- **Wordlists** — Built-in passwords, usernames, and subdomains wordlists
- **76 tests** covering kernel, library, CLI, and command modules
