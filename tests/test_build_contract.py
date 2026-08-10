from pathlib import Path
import re

from app.version import __version__


ROOT = Path(__file__).resolve().parents[1]


def test_buildroot_external_tree_has_valid_identity_and_package_include():
    desc = (ROOT / "buildroot-external-tether" / "external.desc").read_text()
    external_mk = (ROOT / "buildroot-external-tether" / "external.mk").read_text()
    assert "name: TETHER_OS" in desc
    assert "package/*/*.mk" in external_mk


def test_local_package_site_is_canonical_and_has_no_trailing_slash():
    package = (
        ROOT / "buildroot-external-tether" / "package" / "tether-os" /
        "tether-os.mk"
    ).read_text()
    assert "TETHER_OS_SITE = $(realpath $(BR2_EXTERNAL_TETHER_OS_PATH)/..)" in package
    assert "BR2_EXTERNAL_TETHER_OS_PATH)/../" not in package


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
    setup = (ROOT / "setup.py").read_text()
    package = (
        ROOT / "buildroot-external-tether" / "package" / "tether-os" /
        "tether-os.mk"
    ).read_text()
    assert __version__ == "2.0.0rc1"
    assert "app/version.py" in builder
    assert "from app.version import" not in setup
    assert '"app" / "version.py"' in setup
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
    assert "tor 990 tor 990 * /var/lib/tor /bin/false - Tor_daemon" in users
    assert "CONFIG_FEATURE_DEFAULT_PASSWD_ALGO=\"sha512\"" in busybox
    assert "CONFIG_ASH_READ_TIMEOUT=y" in busybox
    for option in ("CONFIG_GETTY=y", "CONFIG_LOGIN=y", "CONFIG_PASSWD=y", "CONFIG_VLOCK=y"):
        assert option in busybox
    assert "# BR2_TARGET_ENABLE_ROOT_LOGIN is not set" in builder
    assert "BR2_ROOTFS_USERS_TABLES" in builder
    assert "BR2_PACKAGE_BUSYBOX_CONFIG_FRAGMENT_FILES" in builder


def test_boot_requires_fail_closed_firewall_and_unprivileged_tor_service():
    overlay = (
        ROOT / "buildroot-external-tether" / "board" / "tether" /
        "rootfs_overlay" / "etc" / "init.d"
    )
    firewall = (overlay / "S01iptables").read_text()
    tor_service = (overlay / "S03tor").read_text()
    boot = (overlay / "rcS").read_text()
    smoke = (ROOT / "scripts" / "qemu-smoke.py").read_text()

    assert "set -e" in firewall
    assert 'iptables -w -P OUTPUT DROP' in firewall
    assert '--uid-owner "$TOR_UID"' in firewall
    assert "set -e" in tor_service
    assert "id -u tor" in tor_service
    assert 'kill -0 "$tor_pid"' in tor_service
    assert "firewall_ready=0" in boot
    assert "restricted mode" in boot
    assert 'child.expect("Tether OS ready.")' in smoke
    for command in ("id -u tor", "pidof tor", "netstat -lnt"):
        assert command in smoke


def test_iso_uses_buildroot_fakeroot_image_for_users_and_ownership():
    builder = (ROOT / "scripts" / "build-distro.sh").read_text()
    post_image = (
        ROOT / "buildroot-external-tether" / "board" / "tether" /
        "post-image.sh"
    ).read_text()

    assert "enable_config BR2_TARGET_ROOTFS_CPIO" in builder
    assert "enable_config BR2_TARGET_ROOTFS_CPIO_GZIP" in builder
    assert 'ROOTFS_CPIO="$BINARIES_DIR/rootfs.cpio.gz"' in post_image
    assert 'cp "$ROOTFS_CPIO" "$ISO_DIR/rootfs.cpio.gz"' in post_image
    assert "find . -print0 | cpio" not in post_image


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
    assert "read -r -t 1" in greeter
    assert "TRAP HUB local login ready" in greeter
    assert "trap-hub-local-login.ready" in greeter
    assert "chown root:root /run/user" in greeter
    assert "chmod 0755 /run/user" in greeter
    assert "chown tether:tether /run/user/1000" in greeter
    assert "chmod 0700 /run/user/1000" in greeter
    assert greeter.index("umask 022") < greeter.index("mkdir -p /run/user")
    assert greeter.index("chmod 0755 /run/user") < greeter.index("mkdir -p /run/user/1000")


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

    assert "export TETHER_BOOT_IMAGE=1" in session
    assert "umask 077" in session
    assert "/etc/tether-edition" in session
    assert '"/dev/tty1"' in session
    assert "TETHER_DESKTOP=1" in session
    assert "exec /usr/bin/tether" in session
    assert "command -v weston" in desktop
    assert "weston --tty=1" in desktop
    assert "trap request_lock USR1" in desktop
    assert "vlock -a </dev/tty1" in desktop
    assert "TETHER_GUI_READY_FILE" in desktop
    assert "trap-hub-lock.active" in desktop
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
    builder = (ROOT / "scripts" / "build-distro.sh").read_text()
    workflow = (ROOT / ".github" / "workflows" / "build-images.yml").read_text()
    assert "edition: [core, desktop]" in workflow
    assert "scripts/qemu-smoke.py" in workflow
    assert '--edition "${{ matrix.edition }}"' in workflow
    assert "--boot-budget 180" in workflow
    assert '--screenshot "$RUNNER_TEMP/tether-os-${{ matrix.edition }}.ppm"' in workflow
    assert "utils/generate-cyclonedx" in builder
    assert '"tether-os-$TETHER_EDITION.sha256"' in builder
    assert 'sha256sum -c "tether-os-${{ matrix.edition }}.sha256"' in workflow
    assert ".sbom.cdx.json" in workflow
    assert "actions/attest@" in workflow
    assert "id-token: write" in workflow
    assert "attestations: write" in workflow
    assert "aquasecurity/trivy-action@" in workflow
    assert "severity: HIGH,CRITICAL" in workflow
    assert "Enforce high-severity vulnerability gate" in workflow


def test_ci_actions_are_pinned_to_immutable_commit_shas():
    for workflow_path in (ROOT / ".github" / "workflows").glob("*.yml"):
        for line in workflow_path.read_text().splitlines():
            if "uses:" not in line:
                continue
            assert re.search(r"uses:\s+[^\s@]+@[0-9a-f]{40}(?:\s|$)", line), (
                f"mutable action reference in {workflow_path.name}: {line.strip()}"
            )


def test_quick_rebuild_cannot_drift_from_the_supported_builder():
    rebuild = (ROOT / "scripts" / "rebuild.sh").read_text()
    assert 'exec "$SCRIPT_DIR/build-distro.sh"' in rebuild
    assert "2024.02.3" not in rebuild
