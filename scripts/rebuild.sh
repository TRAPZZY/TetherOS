#!/bin/bash
# Quick rebuild of Tether OS bootable ISO
set -e
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

BUILDROOT_DIR="$HOME/buildroot-2024.02.3"
TETHER_SRC="$HOME/tether-os"

# Add kernel config fragment if not present
cd "$BUILDROOT_DIR"
if grep -q BR2_LINUX_KERNEL_CONFIG_FRAGMENT_FILES .config; then
    sed -i "/BR2_LINUX_KERNEL_CONFIG_FRAGMENT_FILES/d" .config
fi
echo "BR2_LINUX_KERNEL_CONFIG_FRAGMENT_FILES=$TETHER_SRC/buildroot-external-tether/board/tether/kernel.config" >> .config

# Rebuild everything
make -j$(nproc)

# Show results
echo ""
echo "=== Build Output ==="
ls -lh output/images/
echo ""
echo "=== Test command ==="
echo "  qemu-system-x86_64 -cdrom output/images/tether-os.iso -m 512"
