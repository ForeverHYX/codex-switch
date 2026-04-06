from __future__ import annotations

import os
from pathlib import Path


def _is_executable_file(path: Path) -> bool:
    return path.exists() and os.access(path, os.X_OK)


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
        if candidate.exists() and os.access(candidate, os.X_OK):
            return candidate.resolve()

    raise FileNotFoundError("Unable to locate the real codex binary outside the shim directory")


def resolve_real_codex(stored_path: str, wrapper_dir: Path) -> Path:
    candidate = Path(stored_path).expanduser()
    if _is_executable_file(candidate):
        return candidate.resolve()
    return find_real_codex(wrapper_dir)


def build_instance_env(
    instance_name: str,
    instance_home: Path,
    parent_env: dict[str, str] | None = None,
) -> dict[str, str]:
    env = dict(os.environ if parent_env is None else parent_env)
    env["HOME"] = str(instance_home)
    env["XDG_CONFIG_HOME"] = str(instance_home / ".config")
    env["XDG_CACHE_HOME"] = str(instance_home / ".cache")
    env["XDG_STATE_HOME"] = str(instance_home / ".local" / "state")
    env["CODEX_SWITCH_ACTIVE_INSTANCE"] = instance_name
    return env
