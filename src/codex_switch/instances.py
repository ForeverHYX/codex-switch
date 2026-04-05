from __future__ import annotations

import shutil
from pathlib import Path


def ensure_shared_codex_paths(instance_home: Path, shared_home: Path) -> None:
    for relative in (
        Path(".codex") / "skills",
        Path(".codex") / "superpowers",
    ):
        source = shared_home / relative
        if not source.exists():
            continue
        target = instance_home / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.is_symlink() or target.exists():
            if target.is_dir() and not target.is_symlink():
                shutil.rmtree(target)
            else:
                target.unlink()
        target.symlink_to(source)
