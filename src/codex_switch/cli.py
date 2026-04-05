import typer

app = typer.Typer(no_args_is_help=True)


@app.callback()
def main() -> None:
    """Codex Switch CLI."""


if __name__ == "__main__":
    app()
