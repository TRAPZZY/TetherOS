#!/bin/bash
# Validate BIOS, UEFI, and raw-USB hybrid structures in a release ISO.
set -euo pipefail

ISO="${1:?usage: verify-boot-media.sh ISO REPORT}"
REPORT="${2:?usage: verify-boot-media.sh ISO REPORT}"
if [ ! -s "$ISO" ]; then
    echo "ERROR: release ISO is missing: $ISO" >&2
    exit 1
fi
for tool in xorriso mdir mcopy grub-file; do
    command -v "$tool" >/dev/null 2>&1 || {
        echo "ERROR: media verifier dependency is missing: $tool" >&2
        exit 1
    }
done

WORK_DIR="$(mktemp -d)"
trap 'rm -rf "$WORK_DIR"' EXIT INT TERM
EL_TORITO_REPORT="$WORK_DIR/el-torito.txt"
SYSTEM_AREA_REPORT="$WORK_DIR/system-area.txt"

xorriso -indev "$ISO" -report_el_torito plain > "$EL_TORITO_REPORT"
xorriso -indev "$ISO" -report_system_area plain > "$SYSTEM_AREA_REPORT"
{
    echo "=== EL TORITO ==="
    cat "$EL_TORITO_REPORT"
    echo "=== SYSTEM AREA ==="
    cat "$SYSTEM_AREA_REPORT"
} > "$REPORT"

grep -Eqi 'BIOS' "$EL_TORITO_REPORT"
grep -Eqi 'UEFI' "$EL_TORITO_REPORT"
grep -Eqi 'isohybrid|protective-msdos-label' "$SYSTEM_AREA_REPORT"
grep -Eqi 'GPT' "$SYSTEM_AREA_REPORT"

xorriso -osirrox on -indev "$ISO" \
    -extract /boot/grub/efi.img "$WORK_DIR/efi.img"
mdir -i "$WORK_DIR/efi.img" ::/EFI/BOOT/BOOTX64.EFI >> "$REPORT"
mcopy -i "$WORK_DIR/efi.img" ::/EFI/BOOT/BOOTX64.EFI "$WORK_DIR/BOOTX64.EFI"
grub-file --is-x86_64-efi "$WORK_DIR/BOOTX64.EFI"
echo "BOOT_MEDIA_STRUCTURE=PASS" >> "$REPORT"
