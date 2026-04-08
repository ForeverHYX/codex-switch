from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from codex_switch.models import InstanceConfig
from codex_switch.runtime import build_instance_env


@dataclass(slots=True)
class LoginStatus:
    logged_in: bool
    output: str
    returncode: int


class LoginBootstrapAbortedError(RuntimeError):
    pass


class CodexCommandError(RuntimeError):
    pass


def relogin_message(instance_name: str) -> str:
    return f"Run `codex-switch login {instance_name}` to re-login."


def _run_codex(
    real_codex_path: str | Path,
    instance: InstanceConfig,
    argv: list[str],
    *,
    capture_output: bool = False,
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            [str(real_codex_path), *argv],
            env=build_instance_env(instance.name, Path(instance.home_dir)),
            text=True,
            capture_output=capture_output,
            check=False,
        )
    except FileNotFoundError as exc:
        raise CodexCommandError(f"Unable to launch the real Codex binary: {exc}") from exc


def login_status(real_codex_path: str | Path, instance: InstanceConfig) -> LoginStatus:
    completed = _run_codex(real_codex_path, instance, ["login", "status"], capture_output=True)
    output = "\n".join(
        part for part in (completed.stdout, completed.stderr) if part
    ).strip()
    return LoginStatus(
        logged_in=completed.returncode == 0 and "Logged in" in output,
        output=output,
        returncode=completed.returncode,
    )


def login(real_codex_path: str | Path, instance: InstanceConfig) -> subprocess.CompletedProcess[str]:
    return _run_codex(real_codex_path, instance, ["login"])


def logout(
    real_codex_path: str | Path, instance: InstanceConfig
) -> subprocess.CompletedProcess[str]:
    return _run_codex(real_codex_path, instance, ["logout"])


def _prompt_failure_resolution(
    instance_name: str,
    *,
    allow_skip: bool,
    input_fn: Callable[[str], str],
) -> str:
    choices = "retry, skip, or abort" if allow_skip else "retry or abort"
    while True:
        response = input_fn(
            f"{instance_name} login failed. Type {choices}: "
        ).strip().lower()
        if response in {"r", "retry"}:
            return "retry"
        if allow_skip and response in {"s", "skip"}:
            return "skip"
        if response in {"a", "abort"}:
            return "abort"


def ensure_instance_logged_in(
    real_codex_path: str | Path,
    instance: InstanceConfig,
    *,
    allow_skip: bool,
    input_fn: Callable[[str], str],
    output_fn: Callable[[str], None],
) -> bool:
    current_status = login_status(real_codex_path, instance)
    if current_status.logged_in:
        return True

    while True:
        login(real_codex_path, instance)
        current_status = login_status(real_codex_path, instance)
        if current_status.logged_in:
            return True

        if current_status.output:
            output_fn(current_status.output)

        choice = _prompt_failure_resolution(
            instance.name,
            allow_skip=allow_skip,
            input_fn=input_fn,
        )
        if choice == "retry":
            continue
        if choice == "skip":
            return False
        raise LoginBootstrapAbortedError(
            f"Login aborted for instance {instance.name}"
        )
