#!/bin/bash
# Build Tether OS Linux Distribution
# Run on Ubuntu, Debian, or an equivalent Linux build host.
set -euo pipefail

TETHER_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TETHER_VERSION="$(sed -n 's/^__version__ = "\(.*\)"/\1/p' "$TETHER_ROOT/app/version.py")"
BUILDROOT_VERSION="2025.02.16"
BUILDROOT_ARCHIVE="buildroot-$BUILDROOT_VERSION.tar.xz"
BUILDROOT_SHA256="15305e3d366eeaf4a5ecaf2ed42f685fd6af7fe5dbf1f62e1de5f46ee83225e2"
BUILDROOT_DIR="${BUILDROOT_DIR:-$HOME/buildroot-$BUILDROOT_VERSION}"
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
    qemu-system-x86 xorriso isolinux syslinux-common \
    grub-efi-amd64-bin grub-common dosfstools mtools ovmf

# Step 2: Download Buildroot
echo "[2/6] Downloading Buildroot $BUILDROOT_VERSION..."
if [ ! -f "$BUILDROOT_DIR/Makefile" ]; then
    BUILDROOT_DOWNLOAD="$(mktemp "/tmp/$BUILDROOT_ARCHIVE.XXXXXX")"
    trap 'rm -f "$BUILDROOT_DOWNLOAD"' EXIT INT TERM
    curl --fail --location --retry 3 --retry-delay 2 \
        "https://buildroot.org/downloads/$BUILDROOT_ARCHIVE" \
        --output "$BUILDROOT_DOWNLOAD"
    printf '%s  %s\n' "$BUILDROOT_SHA256" "$BUILDROOT_DOWNLOAD" | sha256sum -c -
    mkdir -p "$BUILDROOT_DIR"
    tar xf "$BUILDROOT_DOWNLOAD" --strip-components=1 -C "$BUILDROOT_DIR"
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

# The boot ISO must consume a Buildroot-generated filesystem image. Custom
# users, numeric ownership, and SUID bits are applied during Buildroot's
# fakeroot image phase and are not guaranteed in output/target.
enable_config BR2_TARGET_ROOTFS_CPIO
enable_config BR2_TARGET_ROOTFS_CPIO_GZIP

# Enable Python 3
enable_config BR2_PACKAGE_PYTHON3
enable_config BR2_PACKAGE_PYTHON3_SSL
enable_config BR2_PACKAGE_PYTHON_PYSOCKS

# Enable Tor
enable_config BR2_PACKAGE_TOR

# Enable iptables
enable_config BR2_PACKAGE_IPTABLES
enable_config BR2_PACKAGE_TETHER_OS

# Match the wired NIC drivers in kernel.config with the deliberately selected
# firmware required by those controllers. Core and Desktop share this baseline.
enable_config BR2_PACKAGE_LINUX_FIRMWARE
enable_config BR2_PACKAGE_LINUX_FIRMWARE_BROADCOM_TIGON3
enable_config BR2_PACKAGE_LINUX_FIRMWARE_BNX2
enable_config BR2_PACKAGE_LINUX_FIRMWARE_RTL_815X
enable_config BR2_PACKAGE_LINUX_FIRMWARE_RTL_8169

if [ "$TETHER_EDITION" = "desktop" ]; then
    echo "[GUI] Enabling the measured Weston/GTK feasibility edition..."

    # PyGObject requires musl or glibc; Weston/GTK require wchar, C++, locale,
    # udev, EGL and a dynamic toolchain.
    disable_config BR2_TOOLCHAIN_BUILDROOT_UCLIBC
    disable_config BR2_TOOLCHAIN_BUILDROOT_GLIBC
    enable_config BR2_TOOLCHAIN_BUILDROOT_MUSL
    enable_config BR2_USE_WCHAR
    enable_config BR2_TOOLCHAIN_BUILDROOT_CXX
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

    # Firmware is selected deliberately for the physical GPU families in the
    # initial Desktop hardware matrix.  Do not enable the entire firmware
    # archive: every shipped blob expands the release and vulnerability scope.
    enable_config BR2_PACKAGE_LINUX_FIRMWARE_AMDGPU
    enable_config BR2_PACKAGE_LINUX_FIRMWARE_I915
    enable_config BR2_PACKAGE_LINUX_FIRMWARE_RADEON
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

# Kconfig may legitimately drop a requested symbol when a dependency is
# missing.  A Desktop build without its realized GUI stack is not a degraded
# edition; it is a failed build.  Verify the final configuration before any
# compilation begins so CI cannot mistake echoed probe text for functionality.
require_config() {
    if ! grep -qx "$1=y" "$CFG"; then
        echo "ERROR: required realized Buildroot option is unavailable: $1" >&2
        exit 1
    fi
}

if [ "$TETHER_EDITION" = "desktop" ]; then
    for option in \
        BR2_TOOLCHAIN_BUILDROOT_CXX \
        BR2_INSTALL_LIBSTDCPP \
        BR2_PACKAGE_MESA3D \
        BR2_PACKAGE_MESA3D_GALLIUM_DRIVER_SWRAST \
        BR2_PACKAGE_MESA3D_OPENGL_EGL \
        BR2_PACKAGE_LIBGTK3 \
        BR2_PACKAGE_LIBGTK3_WAYLAND \
        BR2_PACKAGE_PYTHON_GOBJECT \
        BR2_PACKAGE_WESTON \
        BR2_PACKAGE_WESTON_DRM \
        BR2_PACKAGE_SEATD_DAEMON; do
        require_config "$option"
    done
fi

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

# Fragments express intent; only the realized kernel and target filesystem are
# release evidence. Fail if Kconfig discarded a required physical-boot symbol
# or Buildroot omitted selected firmware.
mapfile -t LINUX_BUILD_DIRS < <(
    find "$BUILDROOT_DIR/output/build" -maxdepth 1 -type d -name 'linux-[0-9]*' -print
)
if [ "${#LINUX_BUILD_DIRS[@]}" -ne 1 ]; then
    echo "ERROR: expected exactly one realized Linux kernel build directory" >&2
    exit 1
fi
LINUX_BUILD_DIR="${LINUX_BUILD_DIRS[0]}"
LINUX_CONFIG="$LINUX_BUILD_DIR/.config"
if [ ! -f "$LINUX_CONFIG" ]; then
    echo "ERROR: realized Linux configuration is unavailable" >&2
    exit 1
fi
require_kernel_config() {
    if ! grep -qx "$1=y" "$LINUX_CONFIG"; then
        echo "ERROR: required realized kernel option is unavailable: $1" >&2
        exit 1
    fi
}
for option in \
    CONFIG_EFI CONFIG_EFI_STUB CONFIG_E1000E CONFIG_IGB CONFIG_IGC \
    CONFIG_R8169 CONFIG_TIGON3 CONFIG_BNX2 CONFIG_USB_RTL8152 \
    CONFIG_USB_XHCI_HCD CONFIG_USB_STORAGE; do
    require_kernel_config "$option"
done
if [ "$TETHER_EDITION" = "desktop" ]; then
    for option in \
        CONFIG_DRM_VIRTIO_GPU CONFIG_DRM_SIMPLEDRM CONFIG_SYSFB_SIMPLEFB \
        CONFIG_DRM_I915 CONFIG_DRM_AMDGPU CONFIG_DRM_RADEON \
        CONFIG_INPUT_EVDEV CONFIG_USB_HID; do
        require_kernel_config "$option"
    done
fi
for firmware_family in bnx2 tigon rtl_nic; do
    if ! find "$BUILDROOT_DIR/output/target/lib/firmware/$firmware_family" \
        -type f -print -quit 2>/dev/null | grep -q .; then
        echo "ERROR: selected $firmware_family firmware is absent" >&2
        exit 1
    fi
done
if [ "$TETHER_EDITION" = "desktop" ]; then
    for firmware_family in amdgpu i915 radeon; do
        if ! find "$BUILDROOT_DIR/output/target/lib/firmware/$firmware_family" \
            -type f -print -quit 2>/dev/null | grep -q .; then
            echo "ERROR: selected $firmware_family firmware is absent" >&2
            exit 1
        fi
    done
fi

# Produce auditable release metadata from the exact configured package graph.
# Buildroot's native generator emits a standards-based CycloneDX SBOM.
IMAGE_DIR="$BUILDROOT_DIR/output/images"
BUILDROOT_INFO="$IMAGE_DIR/tether-os-$TETHER_EDITION.buildroot-info.json"
SBOM="$IMAGE_DIR/tether-os-$TETHER_EDITION.sbom.cdx.json"
CVE_REPORT="$IMAGE_DIR/tether-os-$TETHER_EDITION.cve.cdx.json"
NVD_EVIDENCE="$IMAGE_DIR/tether-os-$TETHER_EDITION.nvd.json"
FULL_SBOM="$BUILDROOT_DIR/output/tether-os-$TETHER_EDITION.full.sbom.cdx.json"
make -s BR2_EXTERNAL="$EXTERNAL_PATH" show-info > "$BUILDROOT_INFO"
utils/generate-cyclonedx \
    --in-file "$BUILDROOT_INFO" \
    --out-file "$FULL_SBOM" \
    --project-name "tether-os-$TETHER_EDITION" \
    --project-version "$TETHER_VERSION"
python3 "$TETHER_ROOT/scripts/filter-runtime-sbom.py" "$FULL_SBOM" "$SBOM"
rm -f "$FULL_SBOM"

# Pin both matrix editions to the same NVD feed commit. CI supplies the
# revision from its preparation job; a local release build resolves it once.
NVD_REMOTE="https://github.com/fkie-cad/nvd-json-data-feeds/"
if [ -z "${NVD_REVISION:-}" ]; then
    NVD_REVISION="$(git ls-remote "$NVD_REMOTE" HEAD | awk '{print $1}')"
fi
if ! printf '%s' "$NVD_REVISION" | grep -Eq '^[0-9a-f]{40}$'; then
    echo "ERROR: NVD_REVISION is not a full Git commit SHA" >&2
    exit 1
fi
NVD_PATH="$BUILDROOT_DIR/dl/buildroot-nvd-$NVD_REVISION"
NVD_REPOSITORY="$NVD_PATH/git"
if [ ! -d "$NVD_REPOSITORY/.git" ]; then
    mkdir -p "$NVD_REPOSITORY"
    git -C "$NVD_REPOSITORY" init
    git -C "$NVD_REPOSITORY" remote add origin "$NVD_REMOTE"
fi
git -C "$NVD_REPOSITORY" fetch --depth=1 origin "$NVD_REVISION"
git -C "$NVD_REPOSITORY" checkout --detach --force FETCH_HEAD
python3 "$TETHER_ROOT/scripts/record-nvd-evidence.py" \
    "$NVD_REPOSITORY" "$NVD_REVISION" "$NVD_EVIDENCE"
support/scripts/cve-check \
    --in-file "$SBOM" \
    --out-file "$CVE_REPORT" \
    --nvd-path "$NVD_PATH" \
    --no-nvd-update

(
    cd "$IMAGE_DIR"
    sha256sum \
        bzImage \
        rootfs.cpio.gz \
        tether-os.iso \
        tether-os.edition \
        "tether-os-$TETHER_EDITION.buildroot-info.json" \
        "tether-os-$TETHER_EDITION.sbom.cdx.json" \
        "tether-os-$TETHER_EDITION.cve.cdx.json" \
        "tether-os-$TETHER_EDITION.nvd.json" > \
        "tether-os-$TETHER_EDITION.sha256"
)

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
