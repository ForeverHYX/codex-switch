from __future__ import annotations

import shutil
from pathlib import Path

from codex_switch.models import InstanceConfig
from codex_switch.paths import instances_dir


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


def create_instances(instance_count: int, shared_home: Path) -> list[InstanceConfig]:
    instances: list[InstanceConfig] = []
    for index in range(1, instance_count + 1):
        name = f"acct-{index:03d}"
        home_dir = instances_dir() / name / "home"
        home_dir.mkdir(parents=True, exist_ok=True)
        ensure_shared_codex_paths(home_dir, shared_home)
        instances.append(
            InstanceConfig(
                name=name,
                order=index,
                home_dir=str(home_dir),
            )
        )
    return instances
