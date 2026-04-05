from __future__ import annotations

import json

from codex_switch.models import AppConfig
from codex_switch.paths import config_path


def load_config() -> AppConfig:
    payload = json.loads(config_path().read_text())
    return AppConfig.from_dict(payload)


def save_config(config: AppConfig) -> None:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config.to_dict(), indent=2, sort_keys=True) + "\n")
