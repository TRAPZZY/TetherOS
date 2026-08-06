#!/bin/sh
# Finalize the Tether OS target filesystem after package installation.
set -eu

rm -f "$TARGET_DIR/etc/init.d/S40network"
rm -f "$TARGET_DIR/etc/init.d/S35iptables"

# Trim development-only Python modules from the initramfs.
rm -rf "$TARGET_DIR"/usr/lib/python3.*/test/
rm -rf "$TARGET_DIR"/usr/lib/python3.*/idlelib/

for script in rcS S01iptables S02network S03tor; do
    chmod +x "$TARGET_DIR/etc/init.d/$script"
done
chmod +x "$TARGET_DIR/usr/bin/tether"
