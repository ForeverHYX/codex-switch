from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from codex_switch.config import ConfigCorruptError, ConfigNotInitializedError, load_config
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


def _fail(message: str) -> int:
    print(f"Error: {message}", file=sys.stderr)
    return 1


def _resolve_instance(config, selected_instance_name: str):
    instance = next(
        (item for item in config.instances if item.name == selected_instance_name),
        None,
    )
    if instance is None:
        raise LookupError(
            f"Selected instance {selected_instance_name!r} is not present in the config"
        )
    return instance


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] in MANAGED_COMMANDS:
        return _fail("Use `codex-switch login` or `codex-switch logout` for account management")

    try:
        config = load_config()
    except ConfigNotInitializedError:
        return _fail("Codex Switch is not initialized. Run `codex-switch init` first.")
    except ConfigCorruptError:
        return _fail("Codex Switch config is corrupt. Remove it and run `codex-switch init` again.")

    try:
        selected = select_best_instance(probe_all_instances(config))
    except FileNotFoundError as exc:
        return _fail(f"Unable to locate the real Codex binary: {exc}")
    except (RuntimeError, StopIteration) as exc:
        return _fail(str(exc))

    try:
        instance = _resolve_instance(config, selected.instance_name)
    except LookupError as exc:
        return _fail(str(exc))

    env = build_instance_env(
        instance_name=instance.name,
        instance_home=Path(instance.home_dir),
    )

    command = REAL_CODEX_ARGV or [config.real_codex_path]
    try:
        completed = subprocess.run(
            [*command, *args],
            env=env,
            check=False,
        )
    except FileNotFoundError as exc:
        return _fail(f"Unable to launch the real Codex binary: {exc}")
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
