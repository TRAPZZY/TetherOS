#!/bin/sh
# Finalize the Tether OS target filesystem after package installation.
set -eu

rm -f "$TARGET_DIR/etc/init.d/S40network"
rm -f "$TARGET_DIR/etc/init.d/S35iptables"

# Trim development-only Python modules from the initramfs.
rm -rf "$TARGET_DIR"/usr/lib/python3.*/test/
rm -rf "$TARGET_DIR"/usr/lib/python3.*/idlelib/

for script in rcS S01iptables S02network S03tor S04trap-hub-control; do
    chmod +x "$TARGET_DIR/etc/init.d/$script"
done
chmod +x "$TARGET_DIR/usr/bin/tether"
chmod +x "$TARGET_DIR/usr/bin/tether-login"
chmod +x "$TARGET_DIR/usr/bin/tether-session"
chmod +x "$TARGET_DIR/usr/bin/tether-desktop"
chmod +x "$TARGET_DIR/usr/bin/tether-gui"

printf '%s\n' "${TETHER_EDITION:-core}" > "$TARGET_DIR/etc/tether-edition"

# Login shells must be explicitly listed on systems that enforce /etc/shells.
grep -qxF '/usr/bin/tether-session' "$TARGET_DIR/etc/shells" 2>/dev/null || \
    echo '/usr/bin/tether-session' >> "$TARGET_DIR/etc/shells"
