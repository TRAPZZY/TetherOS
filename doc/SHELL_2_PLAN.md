# Tether Shell 2 Engineering Plan

**Product:** TetherOS by Trapzzy / TRAP HUB

**Release line:** 2.0

**Status:** Release-candidate implementation and validation

## Product direction

An operating system is more than a boot animation and a command prompt. It is
the trusted layer that starts hardware, creates identities and sessions,
enforces privileges, manages processes and devices, protects secrets, and
recovers predictably when a component fails. TetherOS uses Buildroot for that
Linux foundation and makes the TRAP HUB shell its focused operator interface.

Shell 2 therefore has two jobs:

1. Be an unusually approachable security workstation interface.
2. Respect operating-system boundaries instead of imitating security inside
   Python.

## Research decisions

- **Supported base:** Buildroot 2025.02.16 LTS, checksum pinned. The 2025.02
  series receives the extended LTS maintenance window and is a safer product
  base than the end-of-life 2024.02.3 pin.
- **Authentication owner:** `getty`, `login`, shadow passwords, and `vlock`.
  The Python application must never store a password hash or decide whether a
  password is correct.
- **Graphical stack:** Weston DRM backend with kiosk shell, GTK 3, and
  PyGObject. Weston kiosk shell is explicitly designed for fullscreen,
  single-application systems. It is optional because it materially increases
  image size, build time, driver surface, and hardware-validation work.
- **One engine, multiple views:** Terminal, JSON automation, and GTK call the
  same command registry, parser, results, events, jobs, configuration, and
  lock service. Business logic must not be copied into a GUI.
- **Core first:** The terminal edition is the recovery path and remains the
  default. The Desktop edition may fall back to Core if the compositor cannot
  start.

Primary references:

- [Buildroot manual](https://buildroot.org/downloads/manual/manual.html)
- [Buildroot LTS policy](https://www.buildroot.org/lts.html)
- [Weston kiosk-shell documentation](https://wayland.pages.freedesktop.org/weston/toc/kiosk-shell.html)
- [PyGObject GTK 3 documentation](https://pygobject.gnome.org/tutorials/gtk3.html)
- [`login` manual](https://man7.org/linux/man-pages/man1/login.1.html)
- [`vlock` manual](https://www.man7.org/linux/man-pages/man1/vlock.1.html)

## Experience design

### Boot and session

```text
Linux boot
  -> BusyBox init and services
  -> first-console password enrollment (once per RAM boot)
  -> standard non-root login
  -> edition selector
       -> Core: TRAP HUB terminal
       -> Desktop: Weston kiosk -> GTK Command Deck
  -> inactivity/manual lock
       -> trusted vlock on local display
       -> logout and login re-authentication on serial
```

The user should always know whether the session is authenticated, whether Tor
has actually been verified, whether the lock is available, and whether jobs
are still running. Marketing language must never imply anonymity when route
verification has not succeeded.

### Command Deck

The first screen is operational rather than decorative:

- verified/unverified Tor route and current public IP;
- session uptime and non-root identity;
- lock availability and inactivity timeout;
- running-job count;
- current risk level;
- discoverable commands with detailed and JSON help.

The visual identity remains TRAP HUB: dark graphite surfaces, restrained neon
mint accents, dense monospace output, and clear state labels. Motion is used
only for transitions and active work, never to hide status.

### Command model

Every command has a stable descriptor (name, aliases, category, usage,
summary), produces a result (stdout, exit code, duration, command ID), and
emits lifecycle events. That contract unlocks search, palettes, GUI actions,
plugins, remote automation, audit trails, and tests without replacing the
existing command implementations.

## Delivery milestones and gates

### M0 — Reproducible OS base

- Pin and verify Buildroot 2025.02.16 LTS.
- Produce Core and Desktop configurations from one builder.
- Preserve a terminal recovery path.
- Gate: both images compile on a clean Ubuntu runner.

### M1 — Trusted session boundary

- Disable root login and remove unauthenticated rescue shells.
- Create the fixed non-root `tether` operator.
- Enroll a boot-session password without echoing or logging it.
- Add manual and inactivity lock.
- Replace arbitrary elevation with narrowly allowlisted privileged services.
- Gate: QEMU proves password setup, login, lock, failed access boundary, and
  re-login.

### M2 — Shell engine contracts

- Typed command metadata, results, IDs, durations, and events.
- Detailed help plus JSON discovery.
- Shell-free external process execution.
- Gate: parser, dispatch, exit-code, event-order, and injection regression
  tests.

### M3 — Advanced operator workflow

- Managed background jobs with cancellation and bounded output.
- Command Deck and machine-readable state.
- Credential redaction in history and logs.
- Gate: lifecycle, concurrency, truncation, and privacy regression tests.

### M4 — Optional graphical adapter

- Weston kiosk, GTK/PyGObject UI, fullscreen Command Deck, shared commands,
  and trusted lock handoff.
- Serial console remains Core for diagnostics.
- Gate: Desktop image boots with DRM device, Weston and GTK importable; then
  a visual/QEMU-VNC and two physical-device acceptance pass before promotion
  from feasibility status.

### M5 — Release hardening

- Threat-model review, dependency inventory/SBOM, artifact checksums, upgrade
  notes, recovery tests, performance budgets, and signed release artifacts.
- Gate: no failed automated checks, no unresolved high-severity findings, and
  documented limitations.

## Goal-loop rule

Each increment follows the same closed loop:

1. Define an observable result and failure condition.
2. Implement the smallest coherent vertical slice.
3. Run focused unit/contract tests.
4. Run the complete regression suite.
5. Build on a clean Linux runner.
6. Boot the real artifact in QEMU and exercise the user flow.
7. Review security, failure recovery, logs, and documentation.
8. Fix and repeat until the gate is green; never waive a failed gate silently.

## Post-2.0 opportunities

After the foundation is proven, the highest-impact features are a searchable
command palette, workflow graph/canvas, evidence timeline, replayable runbooks,
signed tool packs, explain-before-run safety previews, live Tor circuit map,
and a remote companion view. These should be plugins over the typed engine,
not new privileged code in the UI.
