from __future__ import annotations

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
        if not target.exists():
            target.symlink_to(source)
