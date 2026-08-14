# Secure Session Design

## Security invariant

TRAP HUB displays state; the operating system authenticates people. Python
never reads a login password, stores a password hash, or implements an unlock
comparison.

## Boot identity

- Root login is disabled in the generated image.
- The normal account is `tether` (UID/GID 1000).
- Its shell is `/usr/bin/tether-session`.
- The account has only the supplemental groups needed for the graphical
  edition (`video`, `input`, and `render`).
- The root filesystem is RAM-backed, so the enrolled password is ephemeral to
  that boot unless a future encrypted persistence feature explicitly changes
  this policy.

## First-boot enrollment

Both local and serial consoles start through `tether-login`. Exactly one
console obtains an atomic setup lock and runs `passwd tether`; other consoles
wait. After setup, `/bin/login tether` performs normal password
authentication. Password input is handled by system tools with terminal echo
disabled and is never written to the TRAP HUB log.

## Lock behavior

### Local Core console

`vlock -a` locks every virtual console and disables console switching until
the `tether` password is accepted.

### Serial console

Virtual-console locking does not provide a reliable serial-terminal security
boundary. A lock therefore ends the shell process. BusyBox `getty` respawns
the greeter and `/bin/login` requires the password again.

### Desktop console

One long-lived, unprivileged shell backend owns `TetherShell`, its state, and
managed jobs for the authenticated Desktop login. Disposable GTK clients use
a mode-0600 Unix socket in the user's mode-0700 runtime directory. Linux
`SO_PEERCRED` authenticates the peer; command and state RPC close before lock.
Only a direct child of the recorded live Desktop supervisor can advance the
lock state, which prevents another same-UID session from reopening it.

The supervisor terminates Weston, releasing tty1, attaches `vlock -a` directly
to tty1, and restarts Weston only after successful authentication. The new GTK
client reconnects to the same backend, so shell state, uptime, and live jobs
continue. If the backend, supervisor, or locker fails, the graphical session
ends instead of reopening unlocked.

Serial access to a Desktop image is a separate authenticated Core session for
diagnostics. Like SSH on a multi-session Linux host, a serial session already
authenticated before a local GUI lock is not itself ended by `vlock`; it
cannot use the Desktop backend while locked. Exposed physical serial ports
must therefore be access-controlled and must not be represented as protected
by the local-display lock.

### Installed application on another OS

The app delegates to the host locker: Windows `LockWorkStation`, Linux
`loginctl`/`xdg-screensaver`, or macOS display sleep. If no trusted locker is
available, the UI reports locking as unavailable rather than presenting a
fake password dialog.

## Privilege boundary

The interactive shell rejects arbitrary `sudo` and `su`. Power actions use a
root-owned FIFO broker that accepts only exact `poweroff` or `reboot` records.
Additional privileged capabilities must be introduced as separate,
allowlisted services with narrow inputs and tests; never by exposing a root
command executor.

## Logging and secrets

- Password- and token-shaped arguments are redacted before history or session
  logging.
- Output from commands known to handle credentials is not persisted.
- Managed job output is capped to prevent disk or memory exhaustion.
- Command execution uses argument vectors (`shell=False`) rather than a host
  command shell.

## Known boundaries

- This design protects each unattended local or serial session through its own
  lock/logout boundary; it is not a global multi-session freeze or full-disk
  encryption and does not protect RAM from an attacker with physical control.
- Desktop support remains a feasibility edition until visual lock/unlock is
  accepted on QEMU-VNC and at least two representative physical GPU/input
  configurations.
- The initial password is per boot. Encrypted, persistent user profiles require
  a separate storage and recovery design.
