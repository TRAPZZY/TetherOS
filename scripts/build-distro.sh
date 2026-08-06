#!/bin/bash
# Build Tether OS Linux Distribution
# Run on Ubuntu, Debian, or an equivalent Linux build host.
set -eu

TETHER_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TETHER_VERSION="$(sed -n 's/^__version__ = "\(.*\)"/\1/p' "$TETHER_ROOT/app/version.py")"
BUILDROOT_VERSION="2025.02.16"
BUILDROOT_ARCHIVE="buildroot-$BUILDROOT_VERSION.tar.xz"
BUILDROOT_SHA256="15305e3d366eeaf4a5ecaf2ed42f685fd6af7fe5dbf1f62e1de5f46ee83225e2"
BUILDROOT_DIR="$HOME/buildroot-$BUILDROOT_VERSION"
TETHER_EDITION="${TETHER_EDITION:-core}"

case "$TETHER_EDITION" in
    core|desktop) ;;
    *) echo "ERROR: TETHER_EDITION must be 'core' or 'desktop'"; exit 2 ;;
esac
export TETHER_EDITION

if [ -z "$TETHER_VERSION" ]; then
    echo "ERROR: Unable to read the TetherOS version from app/version.py"
    exit 2
fi

echo ""
echo "============================================"
echo "   Tether OS Distribution Builder v$TETHER_VERSION"
echo "============================================"
echo "Source: $TETHER_ROOT"
echo "Buildroot: $BUILDROOT_DIR"
echo "Edition: $TETHER_EDITION"
echo ""

# Step 1: Install dependencies
echo "[1/6] Installing build dependencies..."
sudo apt-get update -qq
sudo apt-get install -y -qq \
    build-essential curl file flex bison \
    libncurses-dev libssl-dev libelf-dev \
    bc cpio rsync unzip wget git xz-utils \
    python3 python3-pip python3-venv \
    qemu-system-x86 xorriso isolinux syslinux-common

# Step 2: Download Buildroot
echo "[2/6] Downloading Buildroot $BUILDROOT_VERSION..."
if [ ! -d "$BUILDROOT_DIR" ]; then
    BUILDROOT_DOWNLOAD="$(mktemp "/tmp/$BUILDROOT_ARCHIVE.XXXXXX")"
    trap 'rm -f "$BUILDROOT_DOWNLOAD"' EXIT INT TERM
    curl --fail --location --retry 3 --retry-delay 2 \
        "https://buildroot.org/downloads/$BUILDROOT_ARCHIVE" \
        --output "$BUILDROOT_DOWNLOAD"
    printf '%s  %s\n' "$BUILDROOT_SHA256" "$BUILDROOT_DOWNLOAD" | sha256sum -c -
    tar xf "$BUILDROOT_DOWNLOAD" -C "$HOME"
    rm -f "$BUILDROOT_DOWNLOAD"
    trap - EXIT INT TERM
fi

# Step 3: Prepare config
echo "[3/6] Configuring Tether OS..."
cd "$BUILDROOT_DIR"

# Register the Tether OS external tree before loading any defconfig.
EXTERNAL_PATH="$TETHER_ROOT/buildroot-external-tether"
if [ ! -d "$EXTERNAL_PATH" ]; then
    echo "ERROR: External tree not found at $EXTERNAL_PATH"
    exit 1
fi

# Start from qemu x86_64 defconfig (known-working base)
make BR2_EXTERNAL="$EXTERNAL_PATH" qemu_x86_64_defconfig

# Customize config for Tether OS
CFG="$BUILDROOT_DIR/.config"

enable_config() {
    sed -i "/^$1=/d; /^# $1 is not set/d" "$CFG"
    echo "$1=y" >> "$CFG"
}

disable_config() {
    sed -i "/^$1=/d; /^# $1 is not set/d" "$CFG"
    echo "# $1 is not set" >> "$CFG"
}

# System identity
sed -i 's/BR2_TARGET_GENERIC_HOSTNAME=".*"/BR2_TARGET_GENERIC_HOSTNAME="tether-os"/' "$CFG"
sed -i "s/BR2_TARGET_GENERIC_ISSUE=\".*\"/BR2_TARGET_GENERIC_ISSUE=\"Tether OS v$TETHER_VERSION \\\\l\"/" "$CFG"

# Production sessions are non-root. The boot-time greeter creates an ephemeral
# password for the fixed tether account before standard login is allowed.
sed -i '/BR2_TARGET_ENABLE_ROOT_LOGIN/d' "$CFG"
echo '# BR2_TARGET_ENABLE_ROOT_LOGIN is not set' >> "$CFG"
sed -i '/BR2_TARGET_GENERIC_ROOT_PASSWD/d' "$CFG"
sed -i '/BR2_ROOTFS_USERS_TABLES/d' "$CFG"
echo "BR2_ROOTFS_USERS_TABLES=\"$EXTERNAL_PATH/board/tether/users.txt\"" >> "$CFG"

# Pin the BusyBox authentication and all-VT lock features used by TRAP HUB.
sed -i '/BR2_PACKAGE_BUSYBOX_CONFIG_FRAGMENT_FILES/d' "$CFG"
echo "BR2_PACKAGE_BUSYBOX_CONFIG_FRAGMENT_FILES=\"$EXTERNAL_PATH/board/tether/busybox.fragment\"" >> "$CFG"

# Enable getty on tty1 (serial console from qemu defconfig)
sed -i 's/BR2_TARGET_GENERIC_GETTY_PORT=".*"/BR2_TARGET_GENERIC_GETTY_PORT="tty1"/' "$CFG"
sed -i 's/BR2_TARGET_GENERIC_GETTY_BAUDRATE=".*"/BR2_TARGET_GENERIC_GETTY_BAUDRATE="115200"/' "$CFG"

# Rootfs size
sed -i 's/BR2_TARGET_ROOTFS_EXT2_SIZE=".*"/BR2_TARGET_ROOTFS_EXT2_SIZE="500M"/' "$CFG"

# Enable Python 3
enable_config BR2_PACKAGE_PYTHON3
enable_config BR2_PACKAGE_PYTHON3_SSL
enable_config BR2_PACKAGE_PYTHON_PYSOCKS

# Enable Tor
enable_config BR2_PACKAGE_TOR

# Enable iptables
enable_config BR2_PACKAGE_IPTABLES
enable_config BR2_PACKAGE_TETHER_OS

if [ "$TETHER_EDITION" = "desktop" ]; then
    echo "[GUI] Enabling the measured Weston/GTK feasibility edition..."

    # PyGObject requires musl or glibc; Weston/GTK require wchar, C++, locale,
    # udev, EGL and a dynamic toolchain.
    disable_config BR2_TOOLCHAIN_BUILDROOT_UCLIBC
    disable_config BR2_TOOLCHAIN_BUILDROOT_GLIBC
    enable_config BR2_TOOLCHAIN_BUILDROOT_MUSL
    enable_config BR2_USE_WCHAR
    enable_config BR2_INSTALL_LIBSTDCPP
    enable_config BR2_ENABLE_LOCALE
    disable_config BR2_STATIC_LIBS

    disable_config BR2_ROOTFS_DEVICE_CREATION_STATIC
    disable_config BR2_ROOTFS_DEVICE_CREATION_DYNAMIC_DEVTMPFS
    disable_config BR2_ROOTFS_DEVICE_CREATION_DYNAMIC_MDEV
    enable_config BR2_ROOTFS_DEVICE_CREATION_DYNAMIC_EUDEV

    enable_config BR2_PACKAGE_MESA3D
    enable_config BR2_PACKAGE_MESA3D_GALLIUM_DRIVER_SWRAST
    enable_config BR2_PACKAGE_MESA3D_OPENGL_EGL
    enable_config BR2_PACKAGE_WESTON
    enable_config BR2_PACKAGE_WESTON_DEFAULT_DRM
    enable_config BR2_PACKAGE_WESTON_DRM
    enable_config BR2_PACKAGE_SEATD_DAEMON
    disable_config BR2_PACKAGE_WESTON_SHELL_DESKTOP
    disable_config BR2_PACKAGE_WESTON_SHELL_FULLSCREEN
    disable_config BR2_PACKAGE_WESTON_SHELL_IVI
    enable_config BR2_PACKAGE_WESTON_SHELL_KIOSK
    disable_config BR2_PACKAGE_WESTON_SCREENSHARE
    enable_config BR2_PACKAGE_LIBGTK3
    enable_config BR2_PACKAGE_LIBGTK3_WAYLAND
    enable_config BR2_PACKAGE_PYTHON_GOBJECT
    enable_config BR2_PACKAGE_DEJAVU
fi

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
if [ "$TETHER_EDITION" = "desktop" ]; then
    echo "BR2_LINUX_KERNEL_CONFIG_FRAGMENT_FILES=\"$EXTERNAL_PATH/board/tether/kernel.config $EXTERNAL_PATH/board/tether/kernel-gui.config\"" >> "$CFG"
else
    echo "BR2_LINUX_KERNEL_CONFIG_FRAGMENT_FILES=\"$EXTERNAL_PATH/board/tether/kernel.config\"" >> "$CFG"
fi

# Enable ISO9660 filesystem
# Note: disabled by default — requires isolinux/grub + xorriso
# Build our own ISO via post-image script instead

# Regenerate dependency tree
make BR2_EXTERNAL="$EXTERNAL_PATH" olddefconfig

# Save defconfig for reproducibility
mkdir -p "$EXTERNAL_PATH/configs"
make BR2_EXTERNAL="$EXTERNAL_PATH" \
    BR2_DEFCONFIG="$EXTERNAL_PATH/configs/tether_os_defconfig" savedefconfig

# Step 4: Build
echo "[4/6] Building Tether OS distribution..."
echo "       This will take 15-30 minutes on first build."
echo "       Subsequent builds are much faster."
echo ""
make BR2_EXTERNAL="$EXTERNAL_PATH" -j"$(nproc)"

# Step 5: Verify
echo "[5/6] Build complete!"
ls -lh output/images/
echo ""

# Step 6: Test
echo "[6/6] To test, run:"
echo ""
echo "  qemu-system-x86_64 -cdrom output/images/tether-os.iso -m 512"
echo ""
echo "=== TETHER OS BUILT SUCCESSFULLY ==="
