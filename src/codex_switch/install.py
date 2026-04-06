from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

from codex_switch.paths import shim_dir

ENV_SHIM_DIR = "CODEX_SWITCH_SHIM_DIR"


def _path_entries(path_env: str | None = None) -> list[Path]:
    return [
        Path(entry).expanduser().resolve()
        for entry in (os.environ.get("PATH", "") if path_env is None else path_env).split(os.pathsep)
        if entry
    ]


def _is_user_python_bin(path: Path, home_dir: Path) -> bool:
    try:
        relative = path.relative_to(home_dir)
    except ValueError:
        return False
    return (
        len(relative.parts) == 4
        and relative.parts[0] == "Library"
        and relative.parts[1] == "Python"
        and relative.parts[3] == "bin"
    )


def _is_preferred_install_dir(path: Path, home_dir: Path) -> bool:
    return path in {
        (home_dir / ".local" / "bin").resolve(),
        (home_dir / "bin").resolve(),
    } or _is_user_python_bin(path, home_dir)


def preferred_shim_dir(path_env: str | None = None) -> Path:
    home_dir = Path.home().expanduser().resolve()
    for entry in _path_entries(path_env):
        if _is_preferred_install_dir(entry, home_dir):
            return entry
    return shim_dir()


def shim_path(install_dir: Path | None = None) -> Path:
    return (preferred_shim_dir() if install_dir is None else install_dir) / "codex"


def legacy_shim_path() -> Path:
    return shim_dir() / "codex"


def is_codex_switch_shim(path: Path) -> bool:
    try:
        return "codex_switch.wrapper" in path.read_text()
    except OSError:
        return False


def active_shim_path(path_env: str | None = None) -> Path | None:
    resolved = shutil.which("codex", path=path_env)
    if resolved is None:
        return None
    candidate = Path(resolved).expanduser().resolve()
    if not is_codex_switch_shim(candidate):
        return None
    return candidate


def runtime_wrapper_dir() -> Path:
    override = os.environ.get(ENV_SHIM_DIR)
    if override:
        return Path(override).expanduser().resolve()
    active = active_shim_path()
    if active is not None:
        return active.parent
    return preferred_shim_dir()


def _write_shim(target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        "#!/bin/sh\n"
        f'CODEX_SWITCH_SHIM_DIR="{target.parent}" '
        f'exec "{sys.executable}" -m codex_switch.wrapper "$@"\n'
    )
    os.chmod(target, 0o755)


def install_shim() -> Path:
    target = shim_path()
    if target.exists() and not is_codex_switch_shim(target):
        raise FileExistsError(f"{target} already exists and is not a codex-switch shim")
    _write_shim(target)

    legacy = legacy_shim_path()
    if legacy != target and legacy.exists() and is_codex_switch_shim(legacy):
        legacy.unlink()
    return target


def uninstall_shim() -> Path:
    target = shim_path()
    candidates = [target, legacy_shim_path(), active_shim_path()]
    seen: set[Path] = set()
    for candidate in candidates:
        if candidate is None:
            continue
        resolved = candidate.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        if candidate.exists() and is_codex_switch_shim(candidate):
            candidate.unlink()
    return target
