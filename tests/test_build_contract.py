from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_buildroot_external_tree_has_valid_identity_and_package_include():
    desc = (ROOT / "buildroot-external-tether" / "external.desc").read_text()
    external_mk = (ROOT / "buildroot-external-tether" / "external.mk").read_text()
    assert "name: TETHER_OS" in desc
    assert "package/*/*.mk" in external_mk


def test_boot_launcher_preserves_shell_exit_code():
    launcher = (
        ROOT / "buildroot-external-tether" / "board" / "tether" /
        "rootfs_overlay" / "usr" / "bin" / "tether"
    ).read_text()
    assert "sys.path.insert(0, '/usr/lib/tether-os')" in launcher
    assert "raise SystemExit(main())" in launcher
