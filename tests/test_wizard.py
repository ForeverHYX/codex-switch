import os
import sys
from pathlib import Path

from typer.testing import CliRunner

from codex_switch.cli import app
from codex_switch.models import AppConfig, InstanceConfig
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


def test_cli_init_defaults_to_interactive_detected_codex_path(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("CODEX_SWITCH_HOME", str(tmp_path))
    shared_home = tmp_path / "shared-home"
    monkeypatch.setenv("HOME", str(shared_home))
    detected_codex = tmp_path / "real" / "codex"
    shim_target = shared_home / ".local" / "bin" / "codex"
    seen: dict[str, object] = {}

    monkeypatch.setattr(
        "codex_switch.cli.find_real_codex",
        lambda wrapper_dir: detected_codex,
    )
    monkeypatch.setattr(
        "codex_switch.cli.runtime_wrapper_dir",
        lambda: shared_home / ".local" / "bin",
    )
    monkeypatch.setattr("codex_switch.cli.install_shim", lambda: shim_target)

    def fake_bootstrap_from_prompt(*, real_codex_path, shared_home, input_fn=None, output_fn=print):
        seen["real_codex_path"] = real_codex_path
        seen["shared_home"] = shared_home
        return AppConfig(
            real_codex_path=str(real_codex_path),
            instances=[
                InstanceConfig(
                    name="acct-001",
                    order=1,
                    home_dir=str(tmp_path / "instances" / "acct-001" / "home"),
                )
            ],
        )

    monkeypatch.setattr("codex_switch.cli.bootstrap_from_prompt", fake_bootstrap_from_prompt)

    result = CliRunner().invoke(app, ["init"])

    assert result.exit_code == 0
    assert seen["real_codex_path"] == detected_codex
    assert seen["shared_home"] == shared_home
    assert "Initialized 1 account instances" in result.output
    assert f"Installed codex shim at {shim_target}" in result.output


def test_cli_init_overwrites_existing_state_after_confirmation(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("CODEX_SWITCH_HOME", str(tmp_path))
    shared_home = tmp_path / "shared-home"
    monkeypatch.setenv("HOME", str(shared_home))
    config_path().write_text('{"old": true}')
    stale_file = tmp_path / "instances" / "acct-001" / "home" / "stale.txt"
    stale_file.parent.mkdir(parents=True)
    stale_file.write_text("stale")
    detected_codex = tmp_path / "real" / "codex"
    shim_target = shared_home / ".local" / "bin" / "codex"

    monkeypatch.setattr(
        "codex_switch.cli.find_real_codex",
        lambda wrapper_dir: detected_codex,
    )
    monkeypatch.setattr(
        "codex_switch.cli.runtime_wrapper_dir",
        lambda: shared_home / ".local" / "bin",
    )
    monkeypatch.setattr("codex_switch.cli.install_shim", lambda: shim_target)

    def fake_bootstrap_from_prompt(*, real_codex_path, shared_home, input_fn=None, output_fn=print):
        assert not config_path().exists()
        assert not (tmp_path / "instances").exists()
        return AppConfig(
            real_codex_path=str(real_codex_path),
            instances=[
                InstanceConfig(
                    name="acct-001",
                    order=1,
                    home_dir=str(tmp_path / "instances" / "acct-001" / "home"),
                )
            ],
        )

    monkeypatch.setattr("codex_switch.cli.bootstrap_from_prompt", fake_bootstrap_from_prompt)

    result = CliRunner().invoke(app, ["init"], input="y\n")

    assert result.exit_code == 0
    assert "Overwrite it and rebuild all account instances?" in result.output


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
