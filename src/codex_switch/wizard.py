from __future__ import annotations

import os
from pathlib import Path

from codex_switch.config import save_config
from codex_switch.instances import create_instances
from codex_switch.models import AppConfig
from codex_switch.paths import config_path


def _validate_real_codex_path(real_codex_path: Path) -> None:
    if not real_codex_path.is_file() or not os.access(real_codex_path, os.X_OK):
        raise ValueError(f"{real_codex_path} must point to an executable file")


def initialize_app(
    real_codex_path: Path,
    instance_count: int,
    shared_home: Path,
) -> AppConfig:
    path = config_path()
    if path.exists():
        raise FileExistsError(f"{path} already exists")

    _validate_real_codex_path(real_codex_path)

    config = AppConfig(
        real_codex_path=str(real_codex_path),
        instances=create_instances(instance_count=instance_count, shared_home=shared_home),
    )
    save_config(config)
    return config
