from typer.testing import CliRunner

from codex_switch import __version__
from codex_switch.cli import app


def test_package_exposes_version() -> None:
    assert __version__ == "0.1.4"


def test_cli_app_displays_help() -> None:
    result = CliRunner().invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "Usage" in result.output
