# TetherOS 2.0 Threat Model

**Owner:** Trapzzy / TRAP HUB  
**Scope:** Core and Desktop boot images, authenticated session, TRAP HUB shell,
Tor control path, image build, and release artifacts  
**Review state:** Release-candidate baseline

## Security objectives

TetherOS must:

- require authentication before an operator shell or graphical session opens;
- run normal interactive work as the non-root `tether` account;
- fail closed when a trusted lock, firewall, or Tor verification step is not
  available;
- prevent shell metacharacters in command arguments from becoming host-shell
  execution;
- keep passwords and credential-like values out of history, diagnostics, and
  CI artifacts;
- preserve a serial Core recovery path when the graphical stack fails;
- let a recipient verify the image digest, dependency inventory, and GitHub
  build provenance.

Availability of external websites, Tor exit nodes, DHCP, and unsupported
hardware is outside the system's control. The interface must report those
states accurately instead of converting them into a security success.

## Assets and trust boundaries

| Asset | Boundary and owner |
|---|---|
| Session password and shadow entry | BusyBox `passwd`/`login`; never Python |
| Authenticated terminal or desktop | `getty`, `login`, `vlock`, and the `tether` process tree |
| Root privileges | PID 1, boot services, firewall, Tor service, and two-action power broker |
| Command input and output | Parser, typed command registry, job manager, terminal/GTK adapters |
| Tor protection state | Tor control authentication plus independent egress verification |
| Build inputs and outputs | Pinned Buildroot archive, repository revision, GitHub runner, checksums, SBOM, attestations |
| Desktop shell state | Long-lived same-UID backend; private Unix socket; `SO_PEERCRED`; supervisor-parent lock control |
| Temporary runtime markers | `/run/tether` or mode-0700 `/run/user/1000`; never treated as authentication proof |

The GTK interface and terminal interface are unprivileged views over one shell
engine. GUI readiness files are test/coordination signals only. They do not
grant access and cannot replace `login` or `vlock`.

## Threat actors and assumptions

- A remote network peer can send malformed responses and control a target
  host that the operator scans.
- An unauthenticated person can reach a local keyboard or serial console.
- An authenticated operator can supply hostile command arguments, filenames,
  configuration values, and plugin-like content.
- A dependency mirror or compromised mutable CI action may attempt a supply
  chain substitution.
- A process running as `tether` may attempt to call privileged operations or
  interfere with other processes owned by the same account.

The model does not assume that an attacker already has kernel/root execution.
Once that boundary is lost, the attacker can replace authentication, runtime
markers, firewall rules, and the Python application.

## Threats, controls, and verification

| Threat | Required control | Release evidence |
|---|---|---|
| Unauthenticated console access | Fixed non-root account, root login disabled, password enrollment, standard `login` | QEMU rejects a wrong password, accepts the enrolled password, and returns to login after exit |
| Session left unattended | Manual and inactivity lock; local `vlock -a`; serial session termination and re-login | Unit tests plus Core/Desktop QEMU lock, wrong-password, unlock, and recovery flows |
| Python impersonates authentication | Passwords handled only by OS tools | Static build contracts and architecture review |
| Command injection | Parse into argument vectors; external and background jobs use `shell=False` | Parser/engine injection regression tests |
| Privilege escalation from shell | Reject simulated `sudo`/`su`; exact allowlist for shutdown/reboot broker | Privilege and Buildroot contract tests |
| Secret leakage | Credential-aware redaction and bounded/redacted CI transcript | Privacy, history, and transcript tests |
| False anonymity claim | `verified` only after Tor control and external egress checks | Tor adapter and Command Deck tests |
| GUI bypasses or loses state at lock | Backend closes RPC first; authenticated supervisor stops Weston, enters `vlock`, reopens RPC, then recreates GUI | Unit tests and QEMU prove RPC denial plus VFS/live-job continuity across wrong and correct unlock attempts |
| GUI failure strands recovery | Serial console remains Core; Desktop falls back to Core when Weston exits unexpectedly | Build contract plus QEMU serial diagnostics |
| Image tampering or dependency ambiguity | SHA-256 manifest, Buildroot package metadata, CycloneDX SBOM, signed GitHub provenance/SBOM attestations | Image workflow verifies checksums before attesting and uploading |
| CI action tag replacement | Official actions pinned to immutable commit SHAs | Workflow review and contract tests |
| Multi-console password-setup race | Atomic setup directory, owner PID recovery, timed waiting on the other console | Shell contract and dual-console QEMU flow |

## Residual risk and non-claims

- The current ISO does not implement UEFI Secure Boot or a measured-boot chain.
  GitHub attestations prove CI provenance of a downloaded artifact, not that
  arbitrary firmware loaded that exact artifact.
- The live initramfs intentionally forgets the session password at reboot. It
  is not a persistent multi-user identity system and it has no encrypted
  persistent home directory.
- Processes running as the same `tether` user are not mutually sandboxed.
  Future third-party tool packs require signature verification and a separate
  confinement design before they can be enabled by default.
- A local Desktop lock protects Linux virtual consoles, not a separately
  authenticated physical serial session. Serial ports are a distinct
  multi-session access path and require physical access control or an explicit
  coordinated-session policy in deployments that expose them.
- The firewall constrains the boot image, but no anonymity system can promise
  anonymity against endpoint compromise, operator disclosure, browser
  fingerprinting, malicious documents, or global traffic correlation.
- QEMU validates deterministic virtual hardware. Desktop production promotion
  still requires the documented two-device keyboard, graphics, lock, and
  recovery acceptance pass.
- TetherOS is for authorized security testing. It does not make target access
  lawful and does not remove the operator's responsibility for scope.

## Release decision rule

A failed authentication, lock, firewall, privacy, checksum, SBOM, attestation,
or QEMU boot gate blocks release. A known high-severity vulnerability in a
reachable default component blocks release until it is fixed, removed, or
documented with an approved compensating control. Unsupported hardware may be
listed as a limitation; a failed supported-hardware scenario may not.

Review this model when authentication, privilege boundaries, networking,
update distribution, plugins, persistence, or the graphical stack changes.
