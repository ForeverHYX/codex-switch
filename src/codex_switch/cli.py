from __future__ import annotations

from pathlib import Path

import typer

from codex_switch.auth import (
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
from codex_switch.install import install_shim, uninstall_shim
from codex_switch.models import AppConfig
from codex_switch.paths import config_path, shim_dir
from codex_switch.runtime import resolve_real_codex
from codex_switch.wizard import initialize_app

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
        resolved = resolve_real_codex(config.real_codex_path, shim_dir())
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


@app.command()
def init(
    instance_count: int = typer.Option(..., min=1),
    real_codex_path: Path = typer.Option(..., exists=True, dir_okay=False),
    shared_home: Path = typer.Option(Path.home()),
) -> None:
    try:
        initialize_app(
            real_codex_path=real_codex_path,
            instance_count=instance_count,
            shared_home=shared_home,
        )
    except (FileExistsError, LoginBootstrapAbortedError, ValueError) as exc:
        _fail(str(exc))
    typer.echo(f"Initialized {instance_count} account instances")


@app.command("list")
def list_instances() -> None:
    config = _load_initialized_config()
    for instance in config.instances:
        typer.echo(f"{instance.name}\t{instance.home_dir}")


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
    except LoginBootstrapAbortedError as exc:
        _fail(str(exc))

    if not authenticated:
        _fail(f"Instance {instance_name!r} did not complete login")
    typer.echo(f"Logged in {instance_name}")


@app.command()
def logout(instance_name: str) -> None:
    config = _load_initialized_config()
    instance = _resolve_instance(config, instance_name)
    real_codex_path = _resolve_real_codex_for_management(config)

    run_logout(real_codex_path, instance)
    status = login_status(real_codex_path, instance)
    if status.logged_in:
        _fail(f"Instance {instance_name!r} is still logged in after logout")
    typer.echo(f"Logged out {instance_name}")


@app.command()
def doctor() -> None:
    report = create_doctor_report()
    typer.echo(report.summary())


@app.command("install-shim")
def install_shim_command() -> None:
    target = install_shim()
    typer.echo(f"Installed codex shim at {target}")


@app.command()
def uninstall() -> None:
    target = uninstall_shim()
    typer.echo(f"Removed codex shim at {target}")


if __name__ == "__main__":
    app()
