#!/usr/bin/env python3
"""Fail-closed verification for an extracted TetherOS release bundle.

This validates the locally downloaded files and their SHA-256 manifest. GitHub
attestations are verified separately with ``gh attestation verify`` because
that operation requires network access and the GitHub trust root.
"""

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Dict


EDITIONS = ("core", "desktop")
HASH_LINE = re.compile(r"^([0-9a-f]{64})  ([^\x00\r\n]+)$")
COMMON_REQUIRED = frozenset({
    "bzImage",
    "rootfs.cpio.gz",
    "tether-os.edition",
    "tether-os.iso",
})


class VerificationError(RuntimeError):
    """A release bundle failed a required integrity or format check."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_member(bundle: Path, name: str) -> Path:
    member = Path(name)
    if member.is_absolute() or len(member.parts) != 1 or name in {".", ".."}:
        raise VerificationError(f"unsafe manifest path: {name!r}")
    path = bundle / member
    if path.is_symlink():
        raise VerificationError(f"release member must not be a symlink: {name}")
    if not path.is_file():
        raise VerificationError(f"manifest member is missing: {name}")
    return path


def _parse_manifest(path: Path) -> Dict[str, str]:
    try:
        lines = path.read_text(encoding="ascii").splitlines()
    except (OSError, UnicodeError) as exc:
        raise VerificationError(f"cannot read checksum manifest: {exc}") from exc
    if not lines:
        raise VerificationError("checksum manifest is empty")

    entries = {}
    for number, line in enumerate(lines, 1):
        match = HASH_LINE.fullmatch(line)
        if not match:
            raise VerificationError(f"malformed checksum line {number}")
        expected, name = match.groups()
        if name in entries:
            raise VerificationError(f"duplicate checksum member: {name}")
        entries[name] = expected
    return entries


def _read_json(path: Path, label: str):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise VerificationError(f"invalid {label}: {exc}") from exc


def _check_image_formats(bundle: Path, edition: str) -> None:
    edition_value = (bundle / "tether-os.edition").read_text(
        encoding="ascii"
    ).strip()
    if edition_value != edition:
        raise VerificationError(
            f"edition marker is {edition_value!r}, expected {edition!r}"
        )

    with (bundle / "tether-os.iso").open("rb") as handle:
        handle.seek(16 * 2048 + 1)
        iso_magic = handle.read(5)
    if iso_magic != b"CD001":
        raise VerificationError("tether-os.iso is not a recognized ISO 9660 image")

    with (bundle / "bzImage").open("rb") as handle:
        handle.seek(0x202)
        kernel_magic = handle.read(4)
    if kernel_magic != b"HdrS":
        raise VerificationError("bzImage is missing the Linux setup-header signature")

    with (bundle / "rootfs.cpio.gz").open("rb") as handle:
        rootfs_magic = handle.read(2)
    if rootfs_magic != b"\x1f\x8b":
        raise VerificationError("rootfs.cpio.gz is not gzip data")

    sbom = _read_json(
        bundle / f"tether-os-{edition}.sbom.cdx.json", "CycloneDX SBOM"
    )
    if not isinstance(sbom, dict) or sbom.get("bomFormat") != "CycloneDX":
        raise VerificationError("SBOM does not identify itself as CycloneDX")
    if sbom.get("specVersion") != "1.6":
        raise VerificationError("SBOM is not CycloneDX 1.6")

    cve_report = _read_json(
        bundle / f"tether-os-{edition}.cve.cdx.json",
        "Buildroot CVE report",
    )
    if (
        not isinstance(cve_report, dict)
        or cve_report.get("bomFormat") != "CycloneDX"
        or not isinstance(cve_report.get("vulnerabilities"), list)
    ):
        raise VerificationError("Buildroot CVE report is incomplete")

    nvd = _read_json(
        bundle / f"tether-os-{edition}.nvd.json", "NVD snapshot evidence"
    )
    if (
        not isinstance(nvd, dict)
        or not re.fullmatch(r"[0-9a-f]{40}", str(nvd.get("revision", "")))
        or nvd.get("repository_clean") is not True
        or not isinstance(nvd.get("complete_years"), list)
    ):
        raise VerificationError("NVD snapshot evidence is incomplete")

    inventory = _read_json(
        bundle / f"tether-os-{edition}.buildroot-info.json",
        "Buildroot package inventory",
    )
    if not isinstance(inventory, dict) or not inventory:
        raise VerificationError("Buildroot package inventory is empty")


def verify_bundle(bundle_path, edition: str) -> dict:
    """Verify one extracted artifact directory and return evidence metadata."""
    if edition not in EDITIONS:
        raise VerificationError(f"unsupported edition: {edition}")
    bundle = Path(bundle_path).resolve()
    if not bundle.is_dir():
        raise VerificationError(f"bundle directory does not exist: {bundle}")

    manifest_name = f"tether-os-{edition}.sha256"
    manifest_path = bundle / manifest_name
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise VerificationError(f"checksum manifest is missing: {manifest_name}")
    entries = _parse_manifest(manifest_path)
    required = COMMON_REQUIRED | {
        f"tether-os-{edition}.buildroot-info.json",
        f"tether-os-{edition}.sbom.cdx.json",
        f"tether-os-{edition}.cve.cdx.json",
        f"tether-os-{edition}.nvd.json",
    }
    missing = sorted(required - entries.keys())
    if missing:
        raise VerificationError(
            "checksum manifest does not cover required members: " + ", ".join(missing)
        )

    verified = []
    for name, expected in entries.items():
        member = _safe_member(bundle, name)
        actual = _sha256(member)
        if actual != expected:
            raise VerificationError(
                f"SHA-256 mismatch for {name}: expected {expected}, got {actual}"
            )
        verified.append({"name": name, "sha256": actual, "bytes": member.stat().st_size})

    _check_image_formats(bundle, edition)
    iso = next(item for item in verified if item["name"] == "tether-os.iso")
    return {
        "bundle": str(bundle),
        "edition": edition,
        "iso_sha256": iso["sha256"],
        "manifest": manifest_name,
        "members_verified": len(verified),
        "files": verified,
        "result": "PASS",
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify an extracted TetherOS Core or Desktop release bundle."
    )
    parser.add_argument("bundle", help="directory containing one extracted CI artifact")
    parser.add_argument("--edition", choices=EDITIONS, required=True)
    parser.add_argument(
        "--json", action="store_true", help="emit machine-readable evidence to stdout"
    )
    args = parser.parse_args(argv)
    try:
        report = verify_bundle(args.bundle, args.edition)
    except (OSError, VerificationError) as exc:
        if args.json:
            print(json.dumps({"edition": args.edition, "result": "FAIL", "error": str(exc)}))
        else:
            print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(
            f"PASS: {report['edition']} bundle; "
            f"{report['members_verified']} files; ISO SHA-256 {report['iso_sha256']}"
        )
        print(
            "NEXT: verify both tether-os.iso and the edition SHA-256 manifest "
            "with GitHub attestations before writing USB media."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
