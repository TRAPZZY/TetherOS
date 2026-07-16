# Changelog

## v1.1.1 (2026-07-16)

### Scroll Region Terminal UI

- **ANSI scroll region layout** — Terminal partitioned into fixed header (lines 1-6), scrollable body (lines 7 to h-2), input prompt (h-1), and status bar (h) using DECSTBM (`\033[7;{h-2}r`)
- **Fixed TRAP HUB header** — Static title bar with version, help hint, command count, and separator line; never scrolls away
- **Fixed status bar** — Bottom line shows current IP, rotation count, Tor status, threat level, and active theme
- **Command output scrolls** — Only the middle region scrolls when output exceeds available lines

### Bug Fixes

- **Spinner Unicode crash** — Replaced Braille Unicode spinner chars (`⠋⠙⠹...`) with ASCII `| / - \` to fix `UnicodeEncodeError` on terminals using CP1252 encoding
- **Logo Unicode crash** — Replaced Unicode box-drawing characters (`▐╚╔╝╗═║`) in `TRAP_HUB_LOGO` with pure ASCII art to fix encoding errors on non-UTF-8 terminals
- **Shell entry point** — Added `if __name__ == "__main__": main()` block at the end of `shell.py` so the script runs when invoked directly

### Build System

- **ISO patching** — Rebuilt `tether-os-v26.iso` from v25 by extracting initramfs, patching `shell.py` + `banner.py`, repacking with `find . -print0 | cpio --null -o --format=newc | gzip -9`
- **Initramfs preservation** — Fixed cpio repack to use `-print0` and `--null` flags, preserving symlinks and device nodes

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
