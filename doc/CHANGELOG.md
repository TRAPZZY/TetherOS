# Changelog

## v2.0.0rc1 (2026-08-06)

### Tether Shell 2 and secure session foundation

- Added the TRAP HUB Command Deck in terminal, JSON, and optional GTK forms.
- Replaced root auto-login with a fixed non-root `tether` account, boot-time
  password enrollment, and standard `getty`/`login` authentication.
- Added manual and inactivity locking backed by `vlock`, plus re-authentication
  semantics for serial and graphical sessions.
- Added typed command descriptors, lifecycle events, exit codes, command IDs,
  detailed help, and machine-readable command discovery.
- Added shell-free managed background jobs with bounded output, cancellation,
  and wait/status commands.
- Redacted credential-shaped arguments from history and session logs and
  stopped persisting sensitive command output.
- Added a narrow root-owned power broker instead of arbitrary `sudo` or `su`.
- Upgraded the reproducible image builder to checksum-pinned Buildroot
  2025.02.16 LTS with Core and Desktop editions.
- Added Python 3.11/3.12 quality gates, both-edition image builds, and QEMU
  authentication/lock smoke tests in GitHub Actions.
- Changed ISO assembly to consume Buildroot's fakeroot-generated CPIO image so
  custom users, numeric ownership, device metadata, and SUID permissions are
  present in the booted system.
- Added CycloneDX SBOMs, Buildroot package inventories, release checksums, and
  checksum verification in the image gate.
- Image CI pins official actions to immutable revisions and creates signed
  GitHub build-provenance and SBOM attestations.
- A pinned Trivy SBOM scan now blocks release on reported high or critical
  vulnerabilities while retaining its machine-readable report for diagnosis.
- QEMU now rejects incorrect login/unlock passwords, enforces a boot-to-shell
  budget, exercises the realized Desktop lock lifecycle, and validates a
  nonblank graphical framebuffer.
- Added an explicit threat model and separate physical Desktop acceptance gate.

## v1.1.2 (2026-08-05)

### Production stabilization

- Rebuilt shell parsing and execution around `shlex`, with real pipelines, virtual-filesystem redirection, cycle-safe aliases, and argument-vector subprocess execution.
- Added virtual-filesystem persistence, recursive directory rename, ownership and permission operations, correct disk usage, and glob-based `find` behavior.
- Connected the cron daemon and automatic identity-rotation scheduler to the live shell lifecycle.
- Replaced direct or simulated network paths with shared SOCKS5h transports and Tor-routed HTTP/HTTPS/DNS operations.
- Hardened Tor control authentication, multiline replies, circuit-change verification, daemon startup, and runtime configuration loading.
- Replaced simulated kill-switch state with a fail-closed Buildroot firewall restricted to the Tor service account.
- Removed absolute or fabricated anonymity claims; protected status is now shown only after Tor control and egress verification.
- Repaired the Buildroot external-tree registration, package inclusion, launcher path, target dependencies, and ISO build workflow.
- Unified the CLI, interactive shell, installed launcher, and boot-image entry point on version 1.1.2.
- Added entry-point, shell parser, execution engine, configuration, virtual filesystem, and Buildroot contract tests. The suite now contains 96 passing tests.

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
