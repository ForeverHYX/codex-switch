from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from codex_switch.config import load_config
from codex_switch.models import ProbeResult
from codex_switch.probe import probe_instance
from codex_switch.routing import select_best_instance
from codex_switch.runtime import build_instance_env

MANAGED_COMMANDS = {"login", "logout"}
REAL_CODEX_ARGV: list[str] | None = None


def probe_all_instances(config) -> list[ProbeResult]:
    return [
        probe_instance(config.real_codex_path, instance)
        for instance in config.instances
        if instance.enabled
    ]


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] in MANAGED_COMMANDS:
        raise SystemExit("Use 'codex-switch login' or 'codex-switch doctor' for account management")

    config = load_config()
    selected = select_best_instance(probe_all_instances(config))
    instance = next(item for item in config.instances if item.name == selected.instance_name)
    env = build_instance_env(
        instance_name=instance.name,
        instance_home=Path(instance.home_dir),
    )

    command = REAL_CODEX_ARGV or [config.real_codex_path]
    completed = subprocess.run(
        [*command, *args],
        env=env,
        check=False,
    )
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
