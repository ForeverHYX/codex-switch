from __future__ import annotations

import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from codex_switch.auth import CodexCommandError, LoginBootstrapAbortedError
from codex_switch.config import (
    ConfigCorruptError,
    ConfigNotInitializedError,
    load_config,
    save_config,
)
from codex_switch.install import runtime_wrapper_dir
from codex_switch.models import AppConfig
from codex_switch.models import ProbeResult
from codex_switch.paths import shim_dir
from codex_switch.probe import probe_instance
from codex_switch.routing import select_best_instance
from codex_switch.runtime import build_instance_env, find_real_codex, resolve_real_codex
from codex_switch.wizard import bootstrap_from_prompt

MANAGED_COMMANDS = {"login", "logout"}
REAL_CODEX_ARGV: list[str] | None = None


def probe_all_instances(config) -> list[ProbeResult]:
    instances = [instance for instance in config.instances if instance.enabled]
    with ThreadPoolExecutor(max_workers=max(1, len(instances))) as executor:
        return list(
            executor.map(
                lambda instance: probe_instance(config.real_codex_path, instance),
                instances,
            )
        )


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


def _refresh_real_codex_path(config: AppConfig, resolved_real_codex: Path) -> None:
    resolved_real_codex_str = str(resolved_real_codex)
    if resolved_real_codex_str == config.real_codex_path:
        return
    save_config(
        AppConfig(
            real_codex_path=resolved_real_codex_str,
            instances=config.instances,
        )
    )


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] in MANAGED_COMMANDS:
        return _fail("Use `codex-switch login` or `codex-switch logout` for account management")

    try:
        config = load_config()
    except ConfigNotInitializedError:
        try:
            real_codex_path = find_real_codex(runtime_wrapper_dir())
            bootstrap_from_prompt(real_codex_path=real_codex_path, shared_home=Path.home())
            config = load_config()
        except (CodexCommandError, LoginBootstrapAbortedError) as exc:
            return _fail(str(exc))
        except FileNotFoundError as exc:
            return _fail(f"Unable to locate the real Codex binary: {exc}")
        except ConfigNotInitializedError:
            return _fail("Codex Switch is not initialized. Run `codex-switch init` first.")
    except ConfigCorruptError:
        return _fail("Codex Switch config is corrupt. Remove it and run `codex-switch init` again.")

    try:
        resolved_real_codex = resolve_real_codex(config.real_codex_path, runtime_wrapper_dir())
    except FileNotFoundError as exc:
        return _fail(f"Unable to locate the real Codex binary: {exc}")
    _refresh_real_codex_path(config, resolved_real_codex)

    probe_config = AppConfig(
        real_codex_path=str(resolved_real_codex),
        instances=config.instances,
    )

    try:
        selected = select_best_instance(probe_all_instances(probe_config))
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

    command = REAL_CODEX_ARGV or [str(resolved_real_codex)]
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
