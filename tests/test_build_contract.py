from pathlib import Path

from app.version import __version__


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


def test_buildroot_is_pinned_to_supported_lts_and_verified():
    builder = (ROOT / "scripts" / "build-distro.sh").read_text()
    assert 'BUILDROOT_VERSION="2025.02.16"' in builder
    assert 'BUILDROOT_ARCHIVE="buildroot-$BUILDROOT_VERSION.tar.xz"' in builder
    assert 'BUILDROOT_SHA256="15305e3d366eeaf4a5ecaf2ed42f685fd6af7fe5dbf1f62e1de5f46ee83225e2"' in builder
    assert "sha256sum -c -" in builder
    assert "curl --fail --location --retry 3" in builder


def test_release_version_has_one_authoritative_python_source():
    builder = (ROOT / "scripts" / "build-distro.sh").read_text()
    package = (
        ROOT / "buildroot-external-tether" / "package" / "tether-os" /
        "tether-os.mk"
    ).read_text()
    assert __version__ == "2.0.0rc1"
    assert "app/version.py" in builder
    assert f"TETHER_OS_VERSION = {__version__}" in package


def test_boot_hands_pid1_to_busybox_without_a_rescue_shell():
    init = (
        ROOT / "buildroot-external-tether" / "board" / "tether" /
        "rootfs_overlay" / "init"
    ).read_text()
    assert "exec /sbin/init" in init
    assert "/usr/bin/tether < /dev/console" not in init
    assert "/bin/sh < /dev/console" not in init


def test_build_defines_locked_non_root_session_and_authentication_features():
    board = ROOT / "buildroot-external-tether" / "board" / "tether"
    users = (board / "users.txt").read_text()
    busybox = (board / "busybox.fragment").read_text()
    builder = (ROOT / "scripts" / "build-distro.sh").read_text()

    assert "tether 1000 tether 1000 * /home/tether /usr/bin/tether-session" in users
    assert "CONFIG_FEATURE_DEFAULT_PASSWD_ALGO=\"sha512\"" in busybox
    for option in ("CONFIG_GETTY=y", "CONFIG_LOGIN=y", "CONFIG_PASSWD=y", "CONFIG_VLOCK=y"):
        assert option in busybox
    assert "# BR2_TARGET_ENABLE_ROOT_LOGIN is not set" in builder
    assert "BR2_ROOTFS_USERS_TABLES" in builder
    assert "BR2_PACKAGE_BUSYBOX_CONFIG_FRAGMENT_FILES" in builder


def test_getty_uses_fixed_account_greeter_and_standard_login():
    overlay = (
        ROOT / "buildroot-external-tether" / "board" / "tether" /
        "rootfs_overlay"
    )
    inittab = (overlay / "etc" / "inittab").read_text()
    greeter = (overlay / "usr" / "bin" / "tether-login").read_text()

    assert "getty -L -n -l /usr/bin/tether-login 0 tty1 linux" in inittab
    assert "getty -L -n -l /usr/bin/tether-login 115200 ttyS0 vt100" in inittab
    assert "passwd tether" in greeter
    assert "exec /bin/login tether" in greeter


def test_privilege_broker_has_an_explicit_two_action_allowlist():
    broker = (
        ROOT / "buildroot-external-tether" / "board" / "tether" /
        "rootfs_overlay" / "etc" / "init.d" / "S04trap-hub-control"
    ).read_text()
    assert "poweroff)" in broker
    assert "reboot)" in broker
    assert "unknown action" in broker
    assert "eval " not in broker


def test_gui_is_an_explicit_optional_edition_with_core_as_default():
    builder = (ROOT / "scripts" / "build-distro.sh").read_text()
    assert 'TETHER_EDITION="${TETHER_EDITION:-core}"' in builder
    assert "core|desktop" in builder
    for option in (
        "BR2_PACKAGE_WESTON", "BR2_PACKAGE_WESTON_SHELL_KIOSK",
        "BR2_PACKAGE_LIBGTK3_WAYLAND", "BR2_PACKAGE_PYTHON_GOBJECT",
    ):
        assert f"enable_config {option}" in builder


def test_desktop_session_is_kiosk_scoped_and_falls_back_to_core():
    overlay = (
        ROOT / "buildroot-external-tether" / "board" / "tether" /
        "rootfs_overlay"
    )
    session = (overlay / "usr" / "bin" / "tether-session").read_text()
    desktop = (overlay / "usr" / "bin" / "tether-desktop").read_text()
    weston = (overlay / "etc" / "xdg" / "weston" / "weston.ini").read_text()

    assert "/etc/tether-edition" in session
    assert '"/dev/tty1"' in session
    assert "TETHER_DESKTOP=1" in session
    assert "exec /usr/bin/tether" in session
    assert "command -v weston" in desktop
    assert "weston --tty=1" in desktop
    assert "trap request_lock USR1" in desktop
    assert "vlock -a </dev/tty1" in desktop
    assert "shell=kiosk-shell.so" in weston
    assert "path=/usr/bin/tether-gui" in weston


def test_desktop_kernel_fragment_enables_drm_and_input():
    fragment = (
        ROOT / "buildroot-external-tether" / "board" / "tether" /
        "kernel-gui.config"
    ).read_text()
    assert "CONFIG_DRM=y" in fragment
    assert "CONFIG_DRM_VIRTIO_GPU=y" in fragment
    assert "CONFIG_INPUT_EVDEV=y" in fragment


def test_ci_builds_and_boots_both_editions():
    workflow = (ROOT / ".github" / "workflows" / "build-images.yml").read_text()
    assert "edition: [core, desktop]" in workflow
    assert "scripts/qemu-smoke.py" in workflow
    assert '--edition "${{ matrix.edition }}"' in workflow
