# TetherOS Physical Installation and Acceptance Runbook

**Owner:** Trapzzy / TRAP HUB

**Applies to:** TetherOS 2.0 Core and Desktop boot images
**Purpose:** Safely qualify an exact CI-built image on real x86_64 hardware

This is a live-media test, not a hard-disk installer. TetherOS loads an
initramfs into memory and does not provide a persistent installation workflow.
Removing the USB after a clean shutdown returns the machine to its previous
operating system. The USB itself is completely overwritten when media is
created.

## Release-stopping preconditions

Do not write or boot an image unless every item below is true:

1. The GitHub **quality** workflow passed on the exact commit being tested.
2. Both jobs in the **TetherOS image gates** workflow passed on that commit.
3. The Core and Desktop artifacts were downloaded into different directories;
   their ISO filenames are intentionally identical.
4. Local checksum and format verification passes for each bundle.
5. GitHub's build-provenance and SBOM attestations verify for each ISO.
6. The vulnerability gate reports no unresolved reachable HIGH or CRITICAL
   finding.
7. The release notes identify the test hardware as supported.

An absent file, incomplete manifest, wrong edition marker, failed checksum,
failed attestation, or uncertain workflow revision is a **STOP**, not a warning.
Never substitute an ISO from an older run just to continue testing.

The release image is designed as hybrid media with BIOS ISOLINUX and an x86_64
UEFI fallback loader. Both paths must pass their automated firmware gates. UEFI
Secure Boot is **not** supported: the boot chain is not signed, so Secure Boot
must be disabled for this test and restored afterward.

The initial physical certification scope is x86_64 hardware, wired Ethernet,
and Desktop graphics on selected Intel and AMD GPU families whose exact PCI IDs
are recorded in the evidence. NVIDIA graphics, Wi-Fi boot networking, ARM, and
machines that cannot disable Secure Boot are outside this release's supported
physical matrix. Enabling a kernel option is not certification; QEMU success
does not prove a physical GPU, Ethernet controller, keyboard, or storage path.
Do not widen the support claim until that hardware has completed this runbook.

## People, equipment, and test environment

Use:

- one supported x86_64 machine for the Core physical gate;
- two materially different supported x86_64 machines for Desktop—one selected
  Intel graphics system and one selected AMD graphics system—with different
  keyboard/input-controller families;
- one disposable USB drive per concurrently tested edition (4 GiB or larger);
- a wired Ethernet connection on a network where Tor use and authorized
  security testing are permitted;
- a second computer for artifact verification and evidence capture;
- for the serial-console gate, a real 16550-compatible serial port, a suitable
  null-modem adapter/cable, and a terminal set to 115200 8-N-1 with no flow
  control.

Back up the USB and the host before beginning. Disconnect unnecessary external
drives. Where practical, disconnect internal data drives during first boot.
Never conduct functional security tests against a system or network without
written authorization.

Record the following before changing firmware or writing media:

- tester, date/time/time zone, repository commit, workflow run URL and ID;
- manufacturer, exact model, CPU, RAM, GPU and PCI ID, keyboard/input
  controller, Ethernet controller and PCI ID;
- firmware version, original boot mode, original Secure Boot state and boot
  order;
- USB manufacturer/model/capacity/serial number;
- Core/Desktop bundle SHA-256 and GitHub attestation result.

Across the campaign, exercise at least one physical UEFI boot and one physical
Legacy/CSM boot if both modes will be listed as supported. Record which path
each result covers.

Use a copy of the evidence record at the end of this document for each device.
Do not record the session password, authentication video, secrets, target data,
or full Tor exit IP unless the evidence store is approved for that information.

## 1. Acquire and verify release artifacts

Download the artifacts from the successful image workflow—not from a chat,
cloud-drive mirror, or local developer build. Extract them as, for example,
`artifacts/core` and `artifacts/desktop`. Each directory must contain:

- `tether-os.iso`;
- `bzImage` and `rootfs.cpio.gz`;
- `tether-os.edition`;
- the edition-specific `.sha256` manifest;
- the Buildroot package inventory, CycloneDX SBOM, CVE report, and pinned NVD
  snapshot evidence;
- vulnerability results and Desktop framebuffer evidence where produced.

From a clean checkout of the same commit, run:

```powershell
python scripts/verify-release.py C:\evidence\artifacts\core --edition core --json |
  Tee-Object C:\evidence\core-verification.json
python scripts/verify-release.py C:\evidence\artifacts\desktop --edition desktop --json |
  Tee-Object C:\evidence\desktop-verification.json
```

Linux/macOS equivalent:

```sh
python3 scripts/verify-release.py /evidence/artifacts/core --edition core --json \
  | tee /evidence/core-verification.json
python3 scripts/verify-release.py /evidence/artifacts/desktop --edition desktop --json \
  | tee /evidence/desktop-verification.json
```

The verifier hashes every manifest member and checks the edition marker, ISO
9660 signature, Linux kernel signature, gzip rootfs, inventory JSON, and
CycloneDX identity. It deliberately does not treat hashes inside the same
download as proof of origin. Verify GitHub's signed provenance separately:

```sh
gh auth status
gh attestation verify /evidence/artifacts/core/tether-os.iso \
  --repo TRAPZZY/TetherOS \
  --signer-workflow TRAPZZY/TetherOS/.github/workflows/build-images.yml \
  --source-digest COMMIT_SHA
gh attestation verify /evidence/artifacts/desktop/tether-os.iso \
  --repo TRAPZZY/TetherOS \
  --signer-workflow TRAPZZY/TetherOS/.github/workflows/build-images.yml \
  --source-digest COMMIT_SHA

# The attested manifest binds the kernel, rootfs, SBOM, CVE analysis, and exact
# NVD revision to the same GitHub workflow and commit.
gh attestation verify /evidence/artifacts/core/tether-os-core.sha256 \
  --repo TRAPZZY/TetherOS \
  --signer-workflow TRAPZZY/TetherOS/.github/workflows/build-images.yml \
  --source-digest COMMIT_SHA
gh attestation verify /evidence/artifacts/desktop/tether-os-desktop.sha256 \
  --repo TRAPZZY/TetherOS \
  --signer-workflow TRAPZZY/TetherOS/.github/workflows/build-images.yml \
  --source-digest COMMIT_SHA

# Verify the separate CycloneDX 1.6 SBOM attestation for each ISO as well.
gh attestation verify /evidence/artifacts/core/tether-os.iso \
  --repo TRAPZZY/TetherOS \
  --signer-workflow TRAPZZY/TetherOS/.github/workflows/build-images.yml \
  --source-digest COMMIT_SHA \
  --predicate-type https://cyclonedx.org/bom/v1.6
gh attestation verify /evidence/artifacts/desktop/tether-os.iso \
  --repo TRAPZZY/TetherOS \
  --signer-workflow TRAPZZY/TetherOS/.github/workflows/build-images.yml \
  --source-digest COMMIT_SHA \
  --predicate-type https://cyclonedx.org/bom/v1.6
```

Save the complete verification output. Confirm the attestation identifies
`TRAPZZY/TetherOS`, the expected image workflow, and the exact commit under
test. Also inspect the successful workflow's vulnerability step and archive
its JSON result. A local checksum alone is insufficient.

## 2. Create boot media safely

> **DESTRUCTIVE DEVICE OPERATION:** The selected destination is erased. An
> incorrect device selection can destroy an operating system or backup. Unplug
> other removable media, identify the destination by model, capacity and serial
> number twice, and have a second person confirm it for a production test.

Create separate labeled media for Core and Desktop. Do not copy the ISO as a
normal file onto a filesystem; write it as a raw disk image.

### Windows

Use a reputable raw-image writer that displays the destination model and
capacity and performs post-write validation. In Rufus, select the verified ISO
and exact removable USB, then choose **DD Image mode** if prompted. Recheck the
device after the confirmation dialog appears. Save the validation result or a
screen capture that shows the tool version, source image, and destination—but
not unrelated drive details.

### Linux

First identify the removable drive:

```sh
lsblk -d -o NAME,PATH,SIZE,MODEL,SERIAL,TRAN,RM
```

Unmount every mounted partition on that exact device. Only after two-person
confirmation, replace `/dev/sdX` below with the full verified **whole-device**
path (never a partition such as `/dev/sdX1`):

```sh
sudo dd if=/absolute/path/tether-os.iso of=/dev/sdX bs=4M conv=fsync status=progress
sync
```

Check `dd` returned zero, then read back the ISO-sized prefix and compare it to
the source. One direct method is:

```sh
sudo cmp -n "$(stat -c %s /absolute/path/tether-os.iso)" \
  /absolute/path/tether-os.iso /dev/sdX
```

`cmp` must return zero. Eject the device cleanly.

### macOS

Identify the external disk using `diskutil list`, verify its model and size,
and unmount it with `diskutil unmountDisk /dev/diskN`. After replacing `N` with
the confirmed external whole-disk number, write to its raw device:

```sh
sudo dd if=/absolute/path/tether-os.iso of=/dev/rdiskN bs=4m
sync
diskutil eject /dev/diskN
```

Record the byte count and zero exit status. Use a writer with validation if an
independent full readback is not performed.

## 3. Safe first boot and authentication

1. Start with Ethernet disconnected. Insert the correctly labeled USB.
2. Enter firmware setup and photograph or record original settings. Disable
   Secure Boot, select the UEFI or Legacy/CSM path assigned to this device, and
   use the one-time boot menu rather than permanently changing boot order.
3. Select the USB by its model. Start a stopwatch at boot selection.
4. Confirm TetherOS reaches `TRAP HUB // SECURE SESSION SETUP` without opening
   an unauthenticated shell. Record elapsed time.
5. Press Enter and create a strong, unique **test-only** password. This password
   exists only for the current boot. Do not reuse a real credential.
6. At the first login prompt, intentionally enter a wrong password. It must be
   rejected without revealing the correct password or opening a session.
7. Enter the correct password. Confirm the operator is `tether`, the interface
   identifies TRAP HUB, and `deck --json` reports `"lock_ready": true`.
8. Confirm the edition is the one on the USB label. A Core USB must reach the
   terminal deck; Desktop must reach Weston/GTK after local tty1 login.

Any authentication bypass, root session, wrong edition, crash/rescue shell, or
`lock_ready: false` is a release blocker. Do not attach a network.

## 4. Core functional and security acceptance

Perform this sequence on at least one supported physical system:

1. Run `help --json`, `deck --json`, and `status`. Capture readable output and
   confirm commands return without a traceback.
2. Run `id`. The interactive operator must be UID 1000 (`tether`), not root.
3. Run `killswitch status`. It must report **ENABLED/ENGAGED** before Ethernet
   is connected.
4. Connect approved wired Ethernet. Allow up to five minutes for DHCP and Tor
   bootstrap. Run `status` until Tor Control is **AUTHENTICATED** and Tor Egress
   is **VERIFIED**. An unavailable network must remain visibly unverified.
5. While Ethernet is up, attempt a plain, non-proxied TCP connection:

   ```text
   python3 -c "import socket; socket.create_connection(('1.1.1.1',443),3); print('DIRECT_EGRESS_UNSAFE')"
   ```

   The connection must fail and `DIRECT_EGRESS_UNSAFE` must never print. Then
   rerun `status`; Tor-routed status must still work. Direct egress success is a
   critical kill-switch failure: disconnect Ethernet and stop testing.
6. Record the masked Tor exit identity, run `rotate`, then `status`. Rotation
   must be verified; a fabricated success or unchanged route reported as
   success is a failure.
7. Record `session_uptime_seconds` from `deck --json`. Run `lock`, enter a wrong
   password and verify rejection, then enter the correct password. Rerun the
   deck: the same session must return, its uptime must not reset, and the shell
   must remain functional.
8. Leave the machine completely idle for the configured 600 seconds. It must
   enter the same trusted lock flow. Test wrong and correct passwords again.
9. Run `reboot`. The broker must reboot cleanly, and the next boot must require
   new password enrollment (proving boot-session credentials are ephemeral).
10. Repeat a correct login, then run `shutdown`. The broker must power off
    cleanly without a kernel panic or hang.

Do not test `killswitch off` on a production-candidate image. The acceptance
goal is fail-closed behavior, not demonstrating how to remove it.

## 5. Desktop functional and security acceptance

Run the entire section independently on two supported systems with materially
different GPU and input-controller families, using the exact same verified
Desktop ISO digest.

1. Repeat the first-boot, wrong-password, correct-password, identity,
   kill-switch, Tor verification, direct-egress rejection, rotation, reboot,
   and shutdown tests from the Core section.
2. Confirm Weston/GTK reaches the full-screen TRAP HUB Command Deck within the
   recorded boot budget. Record native panel resolution, actual rendered
   resolution, GPU, connector, keyboard and pointer behavior. There must be no
   blank screen, corrupted frame, unusable scaling, or hidden command field.
3. From the GUI, run `deck --json` and save `session_uptime_seconds`. Execute a
   harmless state-changing shell action and record enough output to recognize
   the same session without capturing sensitive data.
4. Click **LOCK SESSION**. The Command Deck must disappear completely and a
   trusted console lock must own tty1. A wrong password must be rejected. The
   correct password must restore the GUI and the pre-lock shell state; deck
   uptime must not reset. A newly created empty shell is not state continuity.
5. Leave the Desktop untouched for 600 seconds. The same trusted lock,
   wrong-password rejection, correct unlock, and state-continuity requirements
   apply.
6. Before the local lock test, attach the serial test system at 115200 8-N-1.
   The serial console must offer
   authenticated Core diagnostics, reject a wrong password, accept the correct
   boot-session password, and return to login when `lock` is entered. It must
   not unlock, replace, or bypass the local Desktop session. Exit that serial
   session before leaving the local console unattended: it is an independent
   authenticated Linux session, not something `vlock` on tty1 can freeze.
7. Test graphical failure recovery. Enter `killall weston` from the authenticated
   GUI. The screen must recover to an authenticated Core terminal rather than a
   root/rescue shell or reboot loop. Exit the Core shell, log in again, and
   confirm Desktop returns. Mark this as an intentional fault in the evidence.
8. Exercise clean reboot and shutdown last.

Photograph the screen before lock, while locked, after unlock, and after Core
fallback. Never photograph password entry. If the compositor, input stack, or
network driver is unsupported on either selected supported device, Desktop
remains feasibility status.

## 6. Failure containment, rollback, and evidence

If a security assertion fails:

1. Disconnect Ethernet immediately.
2. Photograph or transcribe the exact visible failure without secrets.
3. Record the last successful test ID, timestamps, device details, ISO digest,
   and reproduction steps.
4. Attempt `shutdown` once. If the system is unresponsive, hold the physical
   power button and record that forced shutdown was required.
5. Remove the USB before the next boot.
6. Restore the original firmware boot mode, Secure Boot setting, and boot order.
7. Boot the host OS and confirm its disks and network configuration are intact.
8. Quarantine the USB and evidence; do not reuse the failed image for release.

TetherOS has no in-place rollback because it has no persistent installation.
Recovery is removal of the live USB plus restoration of firmware settings. If
the USB previously contained data, recovery depends on the backup taken before
the destructive write.

Store evidence under a directory named with commit, edition, device and date.
Retain the workflow URL, verifier JSON, attestation output, media-writer result,
hardware record, timed test record, photos and defect references. Hash the
evidence directory or package after capture. Redact session passwords, tokens,
full IP addresses, SSIDs, serial numbers when not operationally necessary, and
any authorized-target data before broader sharing.

## Pass/fail and promotion rules

**Core release candidate** requires all automated gates. Calling Core
physically qualified or production-ready additionally requires every Core
physical test on at least one device from the supported matrix.

**Desktop production promotion** requires all automated gates plus every
Desktop test on both materially different supported devices. Evidence from
QEMU cannot replace either physical device.

Classify results as follows:

- **BLOCKER:** checksum/provenance failure, authentication bypass, root shell,
  direct non-Tor egress, false Tor verification, lock bypass/failure, password
  disclosure, unexpected persistent-disk write, or corrupted host state.
- **FAIL:** a required supported boot, driver, GUI, input, recovery, reboot or
  shutdown scenario does not work or cannot be evidenced.
- **LIMITATION:** a tested scenario is explicitly outside the published support
  matrix and security remains fail-closed. A failure on targeted supported
  hardware may not be relabeled as a limitation.
- **PASS:** observed output meets the criterion and required evidence exists.

No edition is “production ready” while a required row is unchecked, marked
`NOT TESTED`, or supported only by an assumption.

## Per-device evidence record

Copy this section into a new file for each device. Use `PASS`, `FAIL`,
`BLOCKER`, or `NOT TESTED`; never prefill results.

### Release identity

| Field | Recorded value |
|---|---|
| Tester / date / time zone | |
| Edition | |
| Git commit | |
| Quality workflow URL / conclusion | |
| Image workflow URL / job / conclusion | |
| ISO SHA-256 | |
| Local verifier result / evidence path | |
| Provenance attestation result / evidence path | |
| SBOM attestation result / evidence path | |
| Vulnerability report result / evidence path | |
| Media writer/version/validation | |

### Hardware identity

| Field | Recorded value |
|---|---|
| Manufacturer / exact model | |
| CPU / RAM | |
| GPU / PCI ID / connector | |
| Keyboard and pointer / controller | |
| Ethernet controller / PCI ID | |
| Serial controller / adapter | |
| Firmware version / UEFI or Legacy/CSM path | |
| Original and test Secure Boot state | |
| USB model / capacity / asset ID | |

### Acceptance results

| ID | Criterion | Result | Evidence / elapsed time / defect |
|---|---|---|---|
| P01 | Verified artifact, manifest and attestations | | |
| P02 | Raw-media write and validation | | |
| P03 | Boot reaches secure setup without auth bypass | | |
| P04 | Wrong login rejected; correct login accepted | | |
| P05 | Non-root `tether`; correct edition; lock ready | | |
| P06 | Kill switch engaged before network | | |
| P07 | Tor control authenticated and egress verified | | |
| P08 | Plain direct egress rejected | | |
| P09 | Verified Tor rotation | | |
| P10 | Manual lock, wrong rejection, correct unlock, state continuity | | |
| P11 | 600-second idle lock and state continuity | | |
| P12 | Desktop render/input/native resolution (Desktop only) | | |
| P13 | Authenticated serial Core diagnostics (Desktop only) | | |
| P14 | Compositor failure falls back safely (Desktop only) | | |
| P15 | Clean reboot and fresh password enrollment | | |
| P16 | Clean shutdown | | |
| P17 | Firmware restored and host OS unaffected | | |

### Decision

- Overall result:
- Release/promotion decision:
- Open blocker/failure IDs:
- Approved limitations and owner:
- Tester signature/date:
- Independent reviewer signature/date:
