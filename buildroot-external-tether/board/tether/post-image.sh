#!/bin/sh
# Post-image script — create bootable Tether OS ISO
set -e

echo "  [ISO] Creating bootable ISO..."

ISO_DIR="$BINARIES_DIR/iso_root"
ISOHDPFX="/usr/lib/ISOLINUX/isohdpfx.bin"
ISOLINUX_BIN="/usr/lib/ISOLINUX/isolinux.bin"
LDLINUX_C32="/usr/lib/syslinux/modules/bios/ldlinux.c32"

rm -rf "$ISO_DIR"
mkdir -p "$ISO_DIR/isolinux"

cp "$BINARIES_DIR/bzImage" "$ISO_DIR/"

cd "$TARGET_DIR"
find . -print0 | cpio --null -o --format=newc | gzip -9 > "$ISO_DIR/rootfs.cpio.gz"
cd "$OLDPWD"

cp "$ISOLINUX_BIN" "$ISO_DIR/isolinux/"
cp "$LDLINUX_C32" "$ISO_DIR/isolinux/"

if [ "${TETHER_EDITION:-core}" = "desktop" ]; then
    BOOT_ARGS="console=ttyS0 console=tty1 net.ifnames=0 vt.global_cursor_default=0"
else
    BOOT_ARGS="console=ttyS0 console=tty1 nomodeset net.ifnames=0"
fi

cat > "$ISO_DIR/isolinux/syslinux.cfg" << CFG
DEFAULT tether
LABEL tether
    LINUX /bzImage
    INITRD /rootfs.cpio.gz
    APPEND $BOOT_ARGS
CFG

xorriso -as mkisofs \
    -o "$BINARIES_DIR/tether-os.iso" \
    -b isolinux/isolinux.bin \
    -c isolinux/boot.cat \
    -no-emul-boot -boot-load-size 4 -boot-info-table \
    -isohybrid-mbr "$ISOHDPFX" \
    "$ISO_DIR" 2>/dev/null

rm -rf "$ISO_DIR"

ISO_SIZE=$(du -sh "$BINARIES_DIR/tether-os.iso" | cut -f1)
echo "  [ISO] tether-os.iso ($ISO_SIZE) ready at $BINARIES_DIR/tether-os.iso"
printf '%s\n' "${TETHER_EDITION:-core}" > "$BINARIES_DIR/tether-os.edition"
