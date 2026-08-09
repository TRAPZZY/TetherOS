# TetherOS Architecture

**Version:** 2.0.0rc1
**Owner:** Trapzzy / TRAP HUB

## System boundary

TetherOS is a Buildroot-generated Linux system with a Python operator shell.
The Linux layer owns boot, users, authentication, devices, processes,
firewalling, Tor, and shutdown. The Python layer owns command interaction,
workflows, status presentation, and network-tool orchestration.

```text
Hardware / QEMU
  -> Linux 6.12 kernel + initramfs
  -> BusyBox init
       -> device, network, firewall, Tor, power-broker services
       -> getty on tty1 and ttyS0
  -> tether-login -> passwd enrollment -> login(tether)
  -> tether-session
       -> Core: app.entrypoint -> TetherShell
       -> Desktop tty1: Weston kiosk -> GTK Command Deck
```

## Build and image layer

`scripts/build-distro.sh` is the supported image entry point. It:

- downloads Buildroot 2025.02.16 LTS and verifies its SHA-256 digest;
- begins with the upstream QEMU x86_64 defconfig;
- applies the TRAP HUB external tree, users table, BusyBox and kernel fragments;
- generates the compressed root filesystem through Buildroot's fakeroot image
  phase, where users, ownership, devices, and special permission bits become
  part of the boot artifact;
- generates either the default `core` image or optional `desktop` image;
- saves the generated defconfig and produces an ISOLINUX ISO.

The Desktop edition adds musl, eudev, Mesa/EGL, DRM/KMS input drivers,
Weston kiosk shell, seatd, GTK 3, PyGObject, and fonts. Core intentionally does
not acquire these dependencies.

## Boot services

| Component | Responsibility |
|---|---|
| `/init` | Mount early pseudo-filesystems, export boot identity, then exec BusyBox init |
| `rcS` | Run ordered system startup scripts |
| `S01iptables` | Install fail-closed firewall policy |
| `S02network` | Bring up loopback and DHCP |
| `S03tor` | Start the Tor service |
| `S04trap-hub-control` | Serve exact allowlisted power requests over a protected FIFO |
| `inittab` | Maintain authenticated greeters on local and serial consoles |

There is no root auto-login and no unauthenticated fallback shell. The operator
account is `tether`, UID 1000. See `SECURE_SESSION.md` for lock behavior.

## Shell engine

```text
Terminal input / GTK input / automation
  -> shell_parser.parse_line
  -> CommandRegistry (descriptors and handlers)
  -> TetherShell dispatch
       -> internal command
       -> external argv process
       -> managed JobManager process
  -> CommandResult (stdout, exit code, duration, command ID)
  -> EventBus (started/completed)
  -> terminal renderer / Command Deck / JSON consumer
```

Key modules:

| Module | Role |
|---|---|
| `app/commanding.py` | Typed descriptors, results, events, and registry |
| `app/shell_parser.py` | Quoting, pipelines, redirection, and background marker parsing |
| `app/shell.py` | Command dispatch, state, interactive terminal, and built-ins |
| `app/jobs.py` | Shell-free background process lifecycle and bounded output |
| `app/deck.py` | Toolkit-neutral Command Deck state and terminal rendering |
| `app/gui.py` | Optional GTK adapter over the same engine |
| `app/security.py` | Trusted host/boot lock backend selection |
| `app/privilege.py` | Narrow client for the boot-image power broker |
| `app/session.py` | Credential-aware history/session log sanitization |
| `kernel/` | Tor control, route probes, rotation, and scheduling |
| `app/commands/` | Reconnaissance, scanning, forensics, wireless, web, and workflow tools |

The command registry remains mapping-compatible for existing commands while
adding stable metadata. External commands always receive an argument vector;
the engine does not invoke a host command shell.

## State and storage

- The boot ISO runs from an initramfs and its password is per boot.
- The Python virtual filesystem is separate from the host filesystem and is
  used by built-in file commands.
- Application configuration is read from `etc/tether.conf` or the installed
  user configuration path.
- Session logs redact credentials and omit sensitive command output.
- Background job output is stored in temporary files and capped at 1 MiB.

## Network and anonymity claims

Application HTTP/DNS operations use SOCKS5h where supported. Tor protected
status is true only after both control-channel authentication and an external
egress check. The UI distinguishes `verified`, `unverified`, and unavailable
states; it does not equate a running process or open port with anonymity.

The boot image also applies a fail-closed iptables policy that permits external
egress only for the Tor service identity. Loopback and established traffic are
handled explicitly.

## Security invariants

- Python does not authenticate login or unlock passwords.
- Normal interactive code runs as non-root.
- Arbitrary `sudo`/`su` execution is rejected.
- Privileged actions use exact, allowlisted service protocols.
- No background command is evaluated by a host shell.
- No claimed lock backend may silently succeed when unavailable.
- GUI failure must retain or recover to the Core terminal path.

## Validation layers

1. Unit tests for parser, engine, VFS, command modules, security, privacy, jobs,
   registry, deck, GUI adapter, and configuration.
2. Static Buildroot contract tests and Python bytecode compilation.
3. Clean Ubuntu builds for Core and Desktop in GitHub Actions.
4. QEMU boot tests for password enrollment, login, edition dependencies,
   Command Deck state, locking, and re-authentication.
5. Physical hardware acceptance before Desktop leaves feasibility status.

The exact delivery gates and follow-on work are tracked in
`SHELL_2_PLAN.md`.
