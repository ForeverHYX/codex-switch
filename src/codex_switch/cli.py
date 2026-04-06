from __future__ import annotations

from pathlib import Path

import typer

from codex_switch.auth import (
    CodexCommandError,
    LoginBootstrapAbortedError,
    ensure_instance_logged_in,
    login_status,
    logout as run_logout,
)
from codex_switch.config import (
    ConfigCorruptError,
    ConfigNotInitializedError,
    load_config,
    save_config,
)
from codex_switch.doctor import create_doctor_report
from codex_switch.install import install_shim, runtime_wrapper_dir, uninstall_shim
from codex_switch.models import AppConfig
from codex_switch.paths import config_path
from codex_switch.rate_limits import (
    FIVE_HOUR_WINDOW_MINS,
    SEVEN_DAY_WINDOW_MINS,
    format_reset_timestamp,
    read_instance_rate_limits,
    select_window_for_duration,
)
from codex_switch.runtime import find_real_codex, resolve_real_codex
from codex_switch.wizard import bootstrap_from_prompt, clear_existing_state, initialize_app

app = typer.Typer(no_args_is_help=True)


@app.callback()
def main() -> None:
    """Codex Switch CLI."""


def _fail(message: str) -> None:
    typer.secho(f"Error: {message}", err=True)
    raise typer.Exit(code=1)


def _load_initialized_config() -> AppConfig:
    try:
        return load_config()
    except ConfigNotInitializedError:
        _fail("Codex Switch is not initialized. Run `codex-switch init` first.")
    except ConfigCorruptError:
        _fail(
            f"Codex Switch config at {config_path()} is corrupt. "
            "Remove it and run `codex-switch init` again."
        )


def _resolve_real_codex_for_management(config: AppConfig) -> str:
    try:
        resolved = resolve_real_codex(config.real_codex_path, runtime_wrapper_dir())
    except FileNotFoundError as exc:
        _fail(f"Unable to locate the real Codex binary: {exc}")

    resolved_str = str(resolved)
    if resolved_str != config.real_codex_path:
        save_config(
            AppConfig(
                real_codex_path=resolved_str,
                instances=config.instances,
            )
        )
    return resolved_str


def _resolve_instance(config: AppConfig, instance_name: str):
    instance = next((item for item in config.instances if item.name == instance_name), None)
    if instance is None:
        _fail(f"Instance {instance_name!r} is not present in the config")
    return instance


def _render_table(headers: list[str], rows: list[list[str]]) -> list[str]:
    widths = [len(header) for header in headers]
    for row in rows:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], len(cell))

    rendered = [
        "  ".join(header.ljust(widths[index]) for index, header in enumerate(headers))
    ]
    for row in rows:
        rendered.append(
            "  ".join(cell.ljust(widths[index]) for index, cell in enumerate(row))
        )
    return rendered


@app.command()
def init(
    instance_count: int | None = typer.Option(None, min=1),
    real_codex_path: Path | None = typer.Option(None, exists=True, dir_okay=False),
    shared_home: Path | None = typer.Option(None),
    force: bool = typer.Option(False, "--force", help="Overwrite any existing configuration."),
) -> None:
    selected_shared_home = Path.home() if shared_home is None else shared_home
    try:
        resolved_real_codex = (
            real_codex_path
            if real_codex_path is not None
            else find_real_codex(runtime_wrapper_dir())
        )
    except FileNotFoundError as exc:
        _fail(f"Unable to locate the real Codex binary: {exc}")

    if config_path().exists():
        should_rebuild = force or typer.confirm(
            f"{config_path()} already exists. Overwrite it and rebuild all account instances?"
        )
        if not should_rebuild:
            _fail("Initialization aborted.")
        clear_existing_state()

    try:
        if instance_count is None:
            config = bootstrap_from_prompt(
                real_codex_path=resolved_real_codex,
                shared_home=selected_shared_home,
                input_fn=input,
                output_fn=typer.echo,
            )
        else:
            config = initialize_app(
                real_codex_path=resolved_real_codex,
                instance_count=instance_count,
                shared_home=selected_shared_home,
                input_fn=input,
                output_fn=typer.echo,
            )
        shim_target = install_shim()
    except (
        CodexCommandError,
        FileExistsError,
        LoginBootstrapAbortedError,
        ValueError,
    ) as exc:
        _fail(str(exc))
    typer.echo(f"Initialized {len(config.instances)} account instances")
    typer.echo(f"Installed codex shim at {shim_target}")


@app.command("list")
def list_instances() -> None:
    config = _load_initialized_config()
    real_codex_path = _resolve_real_codex_for_management(config)

    rows: list[list[str]] = []
    for instance in config.instances:
        result = read_instance_rate_limits(real_codex_path, instance)
        if not result.ok or result.snapshot is None:
            rows.append(
                [
                    instance.name,
                    "unavailable",
                    "-",
                    "unavailable",
                    "-",
                    result.reason or "Unavailable",
                ]
            )
            continue

        five_hour = select_window_for_duration(
            result.snapshot,
            FIVE_HOUR_WINDOW_MINS,
            fallback="primary",
        )
        seven_day = select_window_for_duration(
            result.snapshot,
            SEVEN_DAY_WINDOW_MINS,
            fallback="secondary",
        )

        rows.append(
            [
                instance.name,
                f"{five_hour.remaining_percent}%" if five_hour is not None else "-",
                format_reset_timestamp(five_hour.resets_at) if five_hour is not None else "-",
                f"{seven_day.remaining_percent}%" if seven_day is not None else "-",
                format_reset_timestamp(seven_day.resets_at) if seven_day is not None else "-",
                result.snapshot.plan_type or "ok",
            ]
        )

    for line in _render_table(
        ["INSTANCE", "5H REMAINING", "5H RESET", "7D REMAINING", "7D RESET", "STATUS"],
        rows,
    ):
        typer.echo(line)


@app.command()
def login(instance_name: str) -> None:
    config = _load_initialized_config()
    instance = _resolve_instance(config, instance_name)
    real_codex_path = _resolve_real_codex_for_management(config)

    try:
        authenticated = ensure_instance_logged_in(
            real_codex_path,
            instance,
            allow_skip=False,
            input_fn=input,
            output_fn=typer.echo,
        )
    except (CodexCommandError, LoginBootstrapAbortedError) as exc:
        _fail(str(exc))

    if not authenticated:
        _fail(f"Instance {instance_name!r} did not complete login")
    typer.echo(f"Logged in {instance_name}")


@app.command()
def logout(instance_name: str) -> None:
    config = _load_initialized_config()
    instance = _resolve_instance(config, instance_name)
    real_codex_path = _resolve_real_codex_for_management(config)

    try:
        run_logout(real_codex_path, instance)
        status = login_status(real_codex_path, instance)
    except CodexCommandError as exc:
        _fail(str(exc))
    if status.logged_in:
        _fail(f"Instance {instance_name!r} is still logged in after logout")
    typer.echo(f"Logged out {instance_name}")


@app.command()
def doctor() -> None:
    report = create_doctor_report()
    typer.echo(report.summary())


@app.command("install-shim")
def install_shim_command() -> None:
    try:
        target = install_shim()
    except FileExistsError as exc:
        _fail(str(exc))
    typer.echo(f"Installed codex shim at {target}")


@app.command()
def uninstall() -> None:
    target = uninstall_shim()
    typer.echo(f"Removed codex shim at {target}")


if __name__ == "__main__":
    app()
