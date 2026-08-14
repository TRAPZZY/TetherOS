import hashlib
import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "verify_release", ROOT / "scripts" / "verify-release.py"
)
VERIFY_RELEASE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VERIFY_RELEASE)


def _write_bundle(tmp_path, edition="core"):
    iso = bytearray(16 * 2048 + 8)
    iso[16 * 2048 + 1:16 * 2048 + 6] = b"CD001"
    kernel = bytearray(0x206)
    kernel[0x202:0x206] = b"HdrS"
    files = {
        "tether-os.iso": bytes(iso),
        "bzImage": bytes(kernel),
        "rootfs.cpio.gz": b"\x1f\x8bfixture",
        "tether-os.edition": f"{edition}\n".encode(),
        f"tether-os-{edition}.buildroot-info.json": json.dumps(
            {"busybox": {"version": "fixture"}}
        ).encode(),
        f"tether-os-{edition}.sbom.cdx.json": json.dumps(
            {"bomFormat": "CycloneDX", "specVersion": "1.6"}
        ).encode(),
        f"tether-os-{edition}.cve.cdx.json": json.dumps({
            "bomFormat": "CycloneDX",
            "specVersion": "1.6",
            "components": [],
            "vulnerabilities": [],
        }).encode(),
        f"tether-os-{edition}.nvd.json": json.dumps({
            "revision": "a" * 40,
            "commit_time": "2026-08-12T00:00:00+00:00",
            "repository_clean": True,
            "complete_years": list(range(1999, 2027)),
        }).encode(),
    }
    for name, data in files.items():
        (tmp_path / name).write_bytes(data)
    manifest = "".join(
        f"{hashlib.sha256(data).hexdigest()}  {name}\n"
        for name, data in files.items()
    )
    (tmp_path / f"tether-os-{edition}.sha256").write_text(
        manifest, encoding="ascii"
    )
    return files


def test_verifies_complete_bundle_and_reports_iso_digest(tmp_path):
    files = _write_bundle(tmp_path)

    report = VERIFY_RELEASE.verify_bundle(tmp_path, "core")

    assert report["result"] == "PASS"
    assert report["members_verified"] == 8
    assert report["iso_sha256"] == hashlib.sha256(files["tether-os.iso"]).hexdigest()


def test_rejects_a_tampered_member(tmp_path):
    _write_bundle(tmp_path)
    (tmp_path / "tether-os.iso").write_bytes(b"tampered")

    with pytest.raises(VERIFY_RELEASE.VerificationError, match="SHA-256 mismatch"):
        VERIFY_RELEASE.verify_bundle(tmp_path, "core")


def test_rejects_manifest_path_traversal(tmp_path):
    _write_bundle(tmp_path)
    manifest = tmp_path / "tether-os-core.sha256"
    manifest.write_text(
        manifest.read_text(encoding="ascii") + "0" * 64 + "  ../outside\n",
        encoding="ascii",
    )

    with pytest.raises(VERIFY_RELEASE.VerificationError, match="unsafe manifest path"):
        VERIFY_RELEASE.verify_bundle(tmp_path, "core")


def test_rejects_incomplete_download_bundle(tmp_path):
    _write_bundle(tmp_path)
    manifest = tmp_path / "tether-os-core.sha256"
    manifest.write_text(
        "\n".join(
            line for line in manifest.read_text(encoding="ascii").splitlines()
            if not line.endswith("  bzImage")
        ) + "\n",
        encoding="ascii",
    )

    with pytest.raises(VERIFY_RELEASE.VerificationError, match="does not cover.*bzImage"):
        VERIFY_RELEASE.verify_bundle(tmp_path, "core")


def test_rejects_wrong_edition_marker_even_with_valid_hash(tmp_path):
    files = _write_bundle(tmp_path)
    files["tether-os.edition"] = b"desktop\n"
    (tmp_path / "tether-os.edition").write_bytes(files["tether-os.edition"])
    manifest = "".join(
        f"{hashlib.sha256(data).hexdigest()}  {name}\n"
        for name, data in files.items()
    )
    (tmp_path / "tether-os-core.sha256").write_text(manifest, encoding="ascii")

    with pytest.raises(VERIFY_RELEASE.VerificationError, match="edition marker"):
        VERIFY_RELEASE.verify_bundle(tmp_path, "core")
