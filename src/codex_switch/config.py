from __future__ import annotations

import json

from codex_switch.models import AppConfig
from codex_switch.paths import config_path


class ConfigError(RuntimeError):
    pass


class ConfigNotInitializedError(ConfigError):
    pass


class ConfigCorruptError(ConfigError):
    pass


def load_config() -> AppConfig:
    path = config_path()
    try:
        payload = json.loads(path.read_text())
    except FileNotFoundError as exc:
        raise ConfigNotInitializedError(str(path)) from exc
    except (json.JSONDecodeError, OSError) as exc:
        raise ConfigCorruptError(str(path)) from exc

    try:
        return AppConfig.from_dict(payload)
    except (TypeError, ValueError, KeyError) as exc:
        raise ConfigCorruptError(str(path)) from exc


def save_config(config: AppConfig) -> None:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config.to_dict(), indent=2, sort_keys=True) + "\n")
