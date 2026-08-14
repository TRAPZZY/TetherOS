#!/bin/sh
# Post-image script — create bootable Tether OS ISO
set -e

echo "  [ISO] Creating bootable ISO..."

ISO_DIR="$BINARIES_DIR/iso_root"
ISOHDPFX="/usr/lib/ISOLINUX/isohdpfx.bin"
ISOLINUX_BIN="/usr/lib/ISOLINUX/isolinux.bin"
LDLINUX_C32="/usr/lib/syslinux/modules/bios/ldlinux.c32"
GRUB_MKSTANDALONE="${GRUB_MKSTANDALONE:-grub-mkstandalone}"

rm -rf "$ISO_DIR"
mkdir -p "$ISO_DIR/isolinux" "$ISO_DIR/boot/grub"

cp "$BINARIES_DIR/bzImage" "$ISO_DIR/"

# Buildroot creates this archive under fakeroot, after applying users tables,
# ownership, device nodes, capabilities, and SUID metadata. Never recreate it
# directly from output/target: that directory intentionally lacks those final
# image-time mutations.
ROOTFS_CPIO="$BINARIES_DIR/rootfs.cpio.gz"
if [ ! -s "$ROOTFS_CPIO" ]; then
    echo "ERROR: Buildroot did not produce rootfs.cpio.gz" >&2
    exit 1
fi
cp "$ROOTFS_CPIO" "$ISO_DIR/rootfs.cpio.gz"

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

# Build an x86_64 UEFI fallback loader and place it in a FAT El Torito image.
# The embedded GRUB configuration locates the ISO9660 root by its kernel file,
# so the same image boots from optical media and raw USB storage.
for tool in "$GRUB_MKSTANDALONE" mkfs.vfat mmd mcopy; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        echo "ERROR: UEFI image dependency is unavailable: $tool" >&2
        exit 1
    fi
done

cat > "$ISO_DIR/boot/grub/grub.cfg" << CFG
set default=0
set timeout=0

menuentry "Tether OS" {
    search --no-floppy --file --set=root /bzImage
    linux /bzImage $BOOT_ARGS
    initrd /rootfs.cpio.gz
}
CFG

EFI_LOADER="$ISO_DIR/boot/grub/BOOTX64.EFI"
EFI_IMAGE="$ISO_DIR/boot/grub/efi.img"
"$GRUB_MKSTANDALONE" \
    --format=x86_64-efi \
    --output="$EFI_LOADER" \
    --modules="part_gpt part_msdos fat iso9660 search search_fs_file normal linux" \
    "boot/grub/grub.cfg=$ISO_DIR/boot/grub/grub.cfg"
dd if=/dev/zero of="$EFI_IMAGE" bs=1M count=8 status=none
mkfs.vfat "$EFI_IMAGE" >/dev/null
mmd -i "$EFI_IMAGE" ::/EFI ::/EFI/BOOT
mcopy -i "$EFI_IMAGE" "$EFI_LOADER" ::/EFI/BOOT/BOOTX64.EFI
rm -f "$EFI_LOADER"

xorriso -as mkisofs \
    -o "$BINARIES_DIR/tether-os.iso" \
    -b isolinux/isolinux.bin \
    -c isolinux/boot.cat \
    -no-emul-boot -boot-load-size 4 -boot-info-table \
    -isohybrid-mbr "$ISOHDPFX" \
    -eltorito-alt-boot \
    -e boot/grub/efi.img -no-emul-boot \
    -isohybrid-gpt-basdat \
    "$ISO_DIR"

rm -rf "$ISO_DIR"

ISO_SIZE=$(du -sh "$BINARIES_DIR/tether-os.iso" | cut -f1)
echo "  [ISO] tether-os.iso ($ISO_SIZE) ready at $BINARIES_DIR/tether-os.iso"
printf '%s\n' "${TETHER_EDITION:-core}" > "$BINARIES_DIR/tether-os.edition"
