from __future__ import annotations

import os
from pathlib import Path


def find_real_codex(wrapper_dir: Path) -> Path:
    path_entries = []
    for entry in os.environ.get("PATH", "").split(os.pathsep):
        if not entry:
            continue
        if Path(entry).resolve() == wrapper_dir.resolve():
            continue
        path_entries.append(entry)

    for entry in path_entries:
        candidate = Path(entry) / "codex"
        if candidate.exists():
            return candidate.resolve()

    raise FileNotFoundError("Unable to locate the real codex binary outside the shim directory")


def build_instance_env(
    instance_name: str,
    instance_home: Path,
    parent_env: dict[str, str] | None = None,
) -> dict[str, str]:
    env = dict(parent_env or os.environ)
    env["HOME"] = str(instance_home)
    env["XDG_CONFIG_HOME"] = str(instance_home / ".config")
    env["XDG_CACHE_HOME"] = str(instance_home / ".cache")
    env["XDG_STATE_HOME"] = str(instance_home / ".local" / "state")
    env["CODEX_SWITCH_ACTIVE_INSTANCE"] = instance_name
    return env
