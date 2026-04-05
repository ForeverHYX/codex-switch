from codex_switch.config import load_config, save_config
from codex_switch.models import AppConfig, InstanceConfig


def test_save_and_load_config_round_trip(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("CODEX_SWITCH_HOME", str(tmp_path))
    config = AppConfig(
        real_codex_path="/usr/local/bin/codex",
        instances=[
            InstanceConfig(
                name="acct-001",
                order=1,
                home_dir=str(tmp_path / "instances" / "acct-001" / "home"),
            )
        ],
    )

    save_config(config)
    loaded = load_config()

    assert loaded == config
