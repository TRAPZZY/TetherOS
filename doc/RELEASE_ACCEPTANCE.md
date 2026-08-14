# TetherOS 2.0 Release Acceptance

This checklist separates automated evidence from hardware evidence. A release
may be called **Core release candidate** when all automated gates pass. The
Desktop edition remains **hardware feasibility** until the final two-device
section is completed by a tester with physical machines.

## Automated release gates

- [ ] Python 3.11 and 3.12 regression suite passes from a clean checkout.
- [ ] Core image compiles from the checksum-pinned Buildroot release.
- [ ] Desktop image compiles from the same revision.
- [ ] Generated image, kernel, rootfs, edition marker, package inventory, and
      CycloneDX SBOM/CVE/NVD evidence match their SHA-256 manifest, and the
      manifest's GitHub provenance verifies for the exact commit.
- [ ] Both editions pass BIOS and UEFI boot from optical and hybrid raw-USB
      media; structural inspection confirms both El Torito entries, MBR/GPT,
      and a valid `EFI/BOOT/BOOTX64.EFI`.
- [ ] Core QEMU rejects an incorrect password, accepts the enrolled password,
      exposes the Command Deck, locks, rejects an incorrect re-login, unlocks,
      exits, and returns to login within the boot budget.
- [ ] Desktop QEMU additionally starts Weston/GTK, exposes a DRM device,
      rejects an incorrect `vlock` password, restores the GUI after a correct
      password, and produces a nonblank framebuffer capture.
- [ ] GitHub creates signed build-provenance and SBOM attestations for each ISO.
- [ ] CI diagnostics contain no session password.
- [ ] Threat model and known limitations match the shipped implementation.
- [ ] No unresolved high-severity finding affects a reachable default
      component, and every unscanned runtime component has a current owned
      coverage exception and compensating control.

## Physical Core production gate

Run this section on at least one x86_64 system from the documented supported
hardware matrix, using the exact checksum- and attestation-verified Core ISO:

- [ ] Raw USB boot reaches password enrollment without exposing a rescue shell.
- [ ] Incorrect login is rejected and the correct password opens a non-root
      `tether` session.
- [ ] The fail-closed firewall is engaged before Ethernet is attached.
- [ ] Tor control and egress verification succeed on an approved wired network,
      while a plain direct TCP connection from `tether` remains blocked.
- [ ] Manual and 600-second inactivity locking reject an incorrect password,
      accept the correct password, and retain the active shell session.
- [ ] Verified circuit rotation, reboot, fresh password enrollment, and clean
      shutdown complete successfully.
- [ ] Firmware settings are restored and the host operating system remains
      intact after the USB is removed.

## Physical Desktop promotion gate

Run this section on two materially different x86_64 systems (different GPU or
input controller families) using the exact checksum-verified ISO:

- [ ] USB boot reaches password enrollment and rejects an incorrect login.
- [ ] Keyboard layout can enter the enrolled password reliably.
- [ ] Weston/GTK Command Deck renders at the native display resolution.
- [ ] Manual lock removes the Command Deck and rejects an incorrect password.
- [ ] Correct unlock restores the Command Deck without losing shell state.
- [ ] Inactivity timeout performs the same trusted lock flow.
- [ ] Serial console remains usable for Core diagnostics while Desktop runs.
- [ ] Unexpected compositor termination falls back to Core.
- [ ] Shutdown and reboot broker actions complete cleanly.
- [ ] Results record hardware model, GPU, firmware mode, observed boot time,
      tester, date, ISO SHA-256, and any limitation.

Do not mark unchecked physical items as passed from QEMU evidence. If either
device fails, Desktop stays feasibility status while Core can continue through
its own release decision.

Execution details, destructive-media safeguards, Core hardware qualification,
Tor and direct-egress checks, rollback, evidence fields, and explicit pass/fail
rules are defined in the
[physical installation and acceptance runbook](PHYSICAL_TEST_RUNBOOK.md).
