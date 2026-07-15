#!/bin/sh
# Post-build script — deploy Tether OS + Python deps
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TETHER_SRC="$(cd "$SCRIPT_DIR/../../.." && pwd)"

# Remove conflicting Buildroot default init scripts
rm -f $TARGET_DIR/etc/init.d/S40network
rm -f $TARGET_DIR/etc/init.d/S35iptables

# Deploy Tether OS source tree to target
mkdir -p $TARGET_DIR/usr/lib/tether-os
cp -r $TETHER_SRC/app $TARGET_DIR/usr/lib/tether-os/
cp -r $TETHER_SRC/kernel $TARGET_DIR/usr/lib/tether-os/
cp -r $TETHER_SRC/lib $TARGET_DIR/usr/lib/tether-os/
cp -r $TETHER_SRC/wordlists $TARGET_DIR/usr/lib/tether-os/
cp -r $TETHER_SRC/etc $TARGET_DIR/usr/lib/tether-os/

# Re-apply our Tor config (Buildroot installs a minimal torrc that overwrites ours)
cp -f $TARGET_DIR/usr/lib/tether-os/etc/tor/torrc $TARGET_DIR/etc/tor/torrc 2>/dev/null || true

# Install Python dependencies
pip3 install pysocks --root=$TARGET_DIR 2>/dev/null || true

# Clean up Python to save space
rm -rf $TARGET_DIR/usr/lib/python3.*/test/
rm -rf $TARGET_DIR/usr/lib/python3.*/idlelib/

# Create /init symlink for initramfs boot (kernel runs /init from cpio)
ln -sf sbin/init $TARGET_DIR/init

# Make init scripts executable
chmod +x $TARGET_DIR/etc/init.d/rcS
chmod +x $TARGET_DIR/etc/init.d/S01iptables
chmod +x $TARGET_DIR/etc/init.d/S02network
chmod +x $TARGET_DIR/etc/init.d/S03tor
chmod +x $TARGET_DIR/usr/bin/tether 2>/dev/null || true
