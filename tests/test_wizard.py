import os
import sys
from pathlib import Path

from typer.testing import CliRunner

from codex_switch.cli import app
from codex_switch.paths import config_path
from codex_switch.wizard import initialize_app


def _make_launcher(tmp_path: Path, fake_codex_path: Path) -> Path:
    launcher = tmp_path / "codex"
    launcher.write_text(
        "#!/bin/sh\n"
        f'exec "{sys.executable}" "{fake_codex_path}" "$@"\n'
    )
    os.chmod(launcher, 0o755)
    return launcher


def test_initialize_app_creates_instances_and_config(
    tmp_path, monkeypatch, fake_codex_path: Path
) -> None:
    monkeypatch.setenv("CODEX_SWITCH_HOME", str(tmp_path))
    shared_home = tmp_path / "shared-home"
    (shared_home / ".codex" / "skills").mkdir(parents=True)
    real_codex = _make_launcher(tmp_path, fake_codex_path)

    config = initialize_app(
        real_codex_path=real_codex,
        instance_count=2,
        shared_home=shared_home,
    )

    assert [instance.name for instance in config.instances] == ["acct-001", "acct-002"]
    assert (tmp_path / "instances" / "acct-001" / "home").exists()
    assert (tmp_path / "config.json").exists()
    assert config.instances[0].enabled is True


def test_initialize_app_rejects_non_executable_codex_path(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("CODEX_SWITCH_HOME", str(tmp_path))
    shared_home = tmp_path / "shared-home"
    (shared_home / ".codex" / "skills").mkdir(parents=True)
    real_codex = tmp_path / "codex"
    real_codex.write_text("#!/bin/sh\n")
    real_codex.chmod(0o644)

    try:
        initialize_app(
            real_codex_path=real_codex,
            instance_count=1,
            shared_home=shared_home,
        )
    except ValueError as exc:
        assert "executable file" in str(exc)
    else:
        raise AssertionError("initialize_app should reject a non-executable codex path")

    assert not config_path().exists()


def test_initialize_app_refuses_to_overwrite_existing_config(
    tmp_path, monkeypatch, fake_codex_path: Path
) -> None:
    monkeypatch.setenv("CODEX_SWITCH_HOME", str(tmp_path))
    shared_home = tmp_path / "shared-home"
    (shared_home / ".codex" / "skills").mkdir(parents=True)
    real_codex = _make_launcher(tmp_path, fake_codex_path)

    initialize_app(
        real_codex_path=real_codex,
        instance_count=1,
        shared_home=shared_home,
    )
    initial_config = config_path().read_text()

    try:
        initialize_app(
            real_codex_path=real_codex,
            instance_count=1,
            shared_home=shared_home,
        )
    except FileExistsError as exc:
        assert "already exists" in str(exc)
    else:
        raise AssertionError("initialize_app should refuse to overwrite existing config")

    assert config_path().read_text() == initial_config


def test_cli_init_rejects_non_executable_codex_path(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("CODEX_SWITCH_HOME", str(tmp_path))
    shared_home = tmp_path / "shared-home"
    real_codex = tmp_path / "codex"
    real_codex.write_text("#!/bin/sh\n")
    real_codex.chmod(0o644)

    result = CliRunner().invoke(
        app,
        [
            "init",
            "--instance-count",
            "1",
            "--real-codex-path",
            str(real_codex),
            "--shared-home",
            str(shared_home),
        ],
    )

    assert result.exit_code == 1
    assert "must point to an executable file" in result.output
    assert not config_path().exists()


def test_cli_list_reports_missing_config_helpfully(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("CODEX_SWITCH_HOME", str(tmp_path))

    result = CliRunner().invoke(app, ["list"])

    assert result.exit_code == 1
    assert "Run `codex-switch init` first" in result.output


def test_cli_list_reports_corrupt_config_helpfully(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("CODEX_SWITCH_HOME", str(tmp_path))
    config_path().write_text("{not-json")

    result = CliRunner().invoke(app, ["list"])

    assert result.exit_code == 1
    assert "Remove it and run `codex-switch init` again" in result.output
