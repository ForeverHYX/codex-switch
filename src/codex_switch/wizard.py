from __future__ import annotations

import os
from typing import Callable
from pathlib import Path

from codex_switch.auth import LoginBootstrapAbortedError, ensure_instance_logged_in
from codex_switch.config import save_config
from codex_switch.instances import create_instances
from codex_switch.models import AppConfig
from codex_switch.paths import config_path


def _validate_real_codex_path(real_codex_path: Path) -> None:
    if not real_codex_path.is_file() or not os.access(real_codex_path, os.X_OK):
        raise ValueError(f"{real_codex_path} must point to an executable file")


def prompt_instance_count(
    *,
    input_fn: Callable[[str], str] | None = None,
    output_fn: Callable[[str], None],
) -> int:
    if input_fn is None:
        input_fn = input
    while True:
        raw_value = input_fn("How many Codex account instances should be created? ").strip()
        try:
            instance_count = int(raw_value)
        except ValueError:
            output_fn("Please enter a whole number.")
            continue
        if instance_count < 1:
            output_fn("Please enter at least 1 account instance.")
            continue
        return instance_count


def initialize_app(
    real_codex_path: Path,
    instance_count: int,
    shared_home: Path,
    *,
    allow_skip: bool = True,
    input_fn: Callable[[str], str] | None = None,
    output_fn: Callable[[str], None] = print,
) -> AppConfig:
    if input_fn is None:
        input_fn = input
    path = config_path()
    if path.exists():
        raise FileExistsError(f"{path} already exists")

    _validate_real_codex_path(real_codex_path)
    if instance_count < 1:
        raise ValueError("instance_count must be at least 1")

    instances = create_instances(instance_count=instance_count, shared_home=shared_home)
    for instance in instances:
        authenticated = ensure_instance_logged_in(
            real_codex_path,
            instance,
            allow_skip=allow_skip,
            input_fn=input_fn,
            output_fn=output_fn,
        )
        if not authenticated and not allow_skip:
            raise LoginBootstrapAbortedError(
                f"Login aborted for instance {instance.name}"
            )

    config = AppConfig(
        real_codex_path=str(real_codex_path),
        instances=instances,
    )
    save_config(config)
    return config


def bootstrap_from_prompt(
    real_codex_path: Path,
    shared_home: Path,
    *,
    input_fn: Callable[[str], str] | None = None,
    output_fn: Callable[[str], None] = print,
) -> AppConfig:
    if input_fn is None:
        input_fn = input
    instance_count = prompt_instance_count(
        input_fn=input_fn,
        output_fn=output_fn,
    )
    return initialize_app(
        real_codex_path=real_codex_path,
        instance_count=instance_count,
        shared_home=shared_home,
        allow_skip=True,
        input_fn=input_fn,
        output_fn=output_fn,
    )
