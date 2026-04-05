from __future__ import annotations

from pathlib import Path

import typer

from codex_switch.config import load_config
from codex_switch.wizard import initialize_app

app = typer.Typer(no_args_is_help=True)


@app.callback()
def main() -> None:
    """Codex Switch CLI."""


@app.command()
def init(
    instance_count: int = typer.Option(..., min=1),
    real_codex_path: Path = typer.Option(..., exists=True, dir_okay=False),
    shared_home: Path = typer.Option(Path.home()),
) -> None:
    initialize_app(
        real_codex_path=real_codex_path,
        instance_count=instance_count,
        shared_home=shared_home,
    )
    typer.echo(f"Initialized {instance_count} account instances")


@app.command("list")
def list_instances() -> None:
    config = load_config()
    for instance in config.instances:
        typer.echo(f"{instance.name}\t{instance.home_dir}")


if __name__ == "__main__":
    app()
