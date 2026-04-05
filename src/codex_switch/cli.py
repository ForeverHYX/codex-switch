from __future__ import annotations

from pathlib import Path

import typer

from codex_switch.config import ConfigCorruptError, ConfigNotInitializedError, load_config
from codex_switch.paths import config_path
from codex_switch.wizard import initialize_app

app = typer.Typer(no_args_is_help=True)


@app.callback()
def main() -> None:
    """Codex Switch CLI."""


def _fail(message: str) -> None:
    typer.secho(f"Error: {message}", err=True)
    raise typer.Exit(code=1)


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
    except (FileExistsError, ValueError) as exc:
        _fail(str(exc))
    typer.echo(f"Initialized {instance_count} account instances")


@app.command("list")
def list_instances() -> None:
    try:
        config = load_config()
    except ConfigNotInitializedError:
        _fail("Codex Switch is not initialized. Run `codex-switch init` first.")
    except ConfigCorruptError:
        _fail(
            f"Codex Switch config at {config_path()} is corrupt. "
            "Remove it and run `codex-switch init` again."
        )

    for instance in config.instances:
        typer.echo(f"{instance.name}\t{instance.home_dir}")


if __name__ == "__main__":
    app()
