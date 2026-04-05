import pytest

from codex_switch.config import load_config, save_config
from codex_switch.models import AppConfig, InstanceConfig
from codex_switch.paths import config_path


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
    assert config_path() == tmp_path / "config.json"
    loaded = load_config()

    assert loaded == config


def test_app_config_from_dict_rejects_malformed_instance() -> None:
    with pytest.raises(ValueError):
        AppConfig.from_dict(
            {
                "real_codex_path": "/usr/local/bin/codex",
                "instances": [
                    {
                        "name": "acct-001",
                        "order": "1",
                        "home_dir": "/tmp/home",
                    }
                ],
            }
        )


def test_load_config_distinguishes_missing_and_corrupt_config(
    tmp_path, monkeypatch
) -> None:
    from codex_switch.config import ConfigCorruptError, ConfigNotInitializedError

    monkeypatch.setenv("CODEX_SWITCH_HOME", str(tmp_path))

    with pytest.raises(ConfigNotInitializedError):
        load_config()

    config_path().write_text("{not-json")

    with pytest.raises(ConfigCorruptError):
        load_config()
