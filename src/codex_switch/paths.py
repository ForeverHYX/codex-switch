from __future__ import annotations

import os
from pathlib import Path


ENV_ROOT = "CODEX_SWITCH_HOME"


def state_root() -> Path:
    override = os.environ.get(ENV_ROOT)
    if override:
        return Path(override).expanduser().resolve()
    return Path.home() / ".codex-switch"


def config_path() -> Path:
    return state_root() / "config.json"


def instances_dir() -> Path:
    return state_root() / "instances"


def logs_dir() -> Path:
    return state_root() / "logs"


def shim_dir() -> Path:
    return state_root() / "bin"
