from __future__ import annotations

from pathlib import Path

from codex_switch.config import save_config
from codex_switch.instances import create_instances
from codex_switch.models import AppConfig


def initialize_app(
    real_codex_path: Path,
    instance_count: int,
    shared_home: Path,
) -> AppConfig:
    config = AppConfig(
        real_codex_path=str(real_codex_path),
        instances=create_instances(instance_count=instance_count, shared_home=shared_home),
    )
    save_config(config)
    return config
