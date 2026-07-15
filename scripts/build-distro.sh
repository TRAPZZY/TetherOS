#!/bin/bash
# Build Tether OS Linux Distribution
# Run this inside WSL2 Ubuntu
set -e

TETHER_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BUILDROOT_VERSION="2024.02.3"
BUILDROOT_DIR="$HOME/buildroot-$BUILDROOT_VERSION"

echo ""
echo "============================================"
echo "   Tether OS Distribution Builder v1.1.0"
echo "============================================"
echo "Source: $TETHER_ROOT"
echo "Buildroot: $BUILDROOT_DIR"
echo ""

# Step 1: Install dependencies
echo "[1/6] Installing build dependencies..."
sudo apt-get update -qq
sudo apt-get install -y -qq \
    build-essential curl file flex bison \
    libncurses-dev libssl-dev libelf-dev \
    bc cpio rsync unzip wget git \
    python3 python3-pip python3-venv \
    qemu-system-x86

# Step 2: Download Buildroot
echo "[2/6] Downloading Buildroot $BUILDROOT_VERSION..."
if [ ! -d "$BUILDROOT_DIR" ]; then
    wget -q --show-progress \
        "https://buildroot.org/downloads/buildroot-$BUILDROOT_VERSION.tar.gz" \
        -O /tmp/buildroot.tar.gz
    tar xf /tmp/buildroot.tar.gz -C "$HOME"
    rm /tmp/buildroot.tar.gz
fi

# Step 3: Prepare config
echo "[3/6] Configuring Tether OS..."
cd "$BUILDROOT_DIR"

# Start from qemu x86_64 defconfig (known-working base)
make qemu_x86_64_defconfig

# Point BR2_EXTERNAL at our tree
EXTERNAL_PATH="$TETHER_ROOT/buildroot-external-tether"
if [ ! -d "$EXTERNAL_PATH" ]; then
    echo "ERROR: External tree not found at $EXTERNAL_PATH"
    exit 1
fi

# Customize config for Tether OS
CFG="$BUILDROOT_DIR/.config"

# System identity
sed -i 's/BR2_TARGET_GENERIC_HOSTNAME=".*"/BR2_TARGET_GENERIC_HOSTNAME="tether-os"/' "$CFG"
sed -i 's/BR2_TARGET_GENERIC_ISSUE=".*"/BR2_TARGET_GENERIC_ISSUE="Tether OS v1.1.0 \\l"/' "$CFG"

# Enable getty on tty1 (serial console from qemu defconfig)
sed -i 's/BR2_TARGET_GENERIC_GETTY_PORT=".*"/BR2_TARGET_GENERIC_GETTY_PORT="tty1"/' "$CFG"
sed -i 's/BR2_TARGET_GENERIC_GETTY_BAUDRATE=".*"/BR2_TARGET_GENERIC_GETTY_BAUDRATE="115200"/' "$CFG"

# Rootfs size
sed -i 's/BR2_TARGET_ROOTFS_EXT2_SIZE=".*"/BR2_TARGET_ROOTFS_EXT2_SIZE="500M"/' "$CFG"

# Enable Python 3
grep -q 'BR2_PACKAGE_PYTHON3=y' "$CFG" || echo 'BR2_PACKAGE_PYTHON3=y' >> "$CFG"

# Enable Tor
grep -q 'BR2_PACKAGE_TOR=y' "$CFG" || echo 'BR2_PACKAGE_TOR=y' >> "$CFG"

# Enable iptables
grep -q 'BR2_PACKAGE_IPTABLES=y' "$CFG" || echo 'BR2_PACKAGE_IPTABLES=y' >> "$CFG"

# Rootfs overlay
sed -i '/BR2_ROOTFS_OVERLAY/d' "$CFG"
echo "BR2_ROOTFS_OVERLAY=\"$EXTERNAL_PATH/board/tether/rootfs_overlay\"" >> "$CFG"

# Post-build script
sed -i '/BR2_ROOTFS_POST_BUILD_SCRIPT/d' "$CFG"
echo "BR2_ROOTFS_POST_BUILD_SCRIPT=\"$EXTERNAL_PATH/board/tether/post-build.sh\"" >> "$CFG"

# Post-image script
sed -i '/BR2_ROOTFS_POST_IMAGE_SCRIPT/d' "$CFG"
echo "BR2_ROOTFS_POST_IMAGE_SCRIPT=\"$EXTERNAL_PATH/board/tether/post-image.sh\"" >> "$CFG"

# Kernel config fragment (initramfs support)
sed -i '/BR2_LINUX_KERNEL_CONFIG_FRAGMENT_FILES/d' "$CFG"
echo "BR2_LINUX_KERNEL_CONFIG_FRAGMENT_FILES=\"$EXTERNAL_PATH/board/tether/kernel.config\"" >> "$CFG"

# Enable ISO9660 filesystem
# Note: disabled by default — requires isolinux/grub + xorriso
# Build our own ISO via post-image script instead

# Regenerate dependency tree
make olddefconfig

# Save defconfig for reproducibility
mkdir -p "$EXTERNAL_PATH/configs"
cp "$CFG" "$EXTERNAL_PATH/configs/tether_os_defconfig"

# Step 4: Build
echo "[4/6] Building Tether OS distribution..."
echo "       This will take 15-30 minutes on first build."
echo "       Subsequent builds are much faster."
echo ""
make -j$(nproc)

# Step 5: Verify
echo "[5/6] Build complete!"
ls -lh output/images/
echo ""

# Step 6: Test
echo "[6/6] To test, run:"
echo ""
echo "  qemu-system-x86_64 -cdrom output/images/rootfs.iso9660 -m 512"
echo ""
echo "=== TETHER OS BUILT SUCCESSFULLY ==="
