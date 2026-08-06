from app.config import load_config


def test_config_loader_parses_typed_values(tmp_path):
    path = tmp_path / "tether.conf"
    path.write_text(
        "[tether]\nrotation_interval = 120\nauto_rotate = false\n"
        "[tor]\nhost = 10.0.0.2\nsocks_port = 9150\ncontrol_port = 9151\n"
        "[security]\nlock_enabled = true\nlock_timeout_seconds = 900\n",
        encoding="utf-8",
    )
    config = load_config(path)
    assert config.rotation_interval == 120
    assert config.auto_rotate is False
    assert config.tor_host == "10.0.0.2"
    assert config.tor_socks_port == 9150
    assert config.lock_enabled is True
    assert config.lock_timeout_seconds == 900
