import os
import sys
from pathlib import Path

from typer.testing import CliRunner

from codex_switch.cli import app
from codex_switch.config import save_config
from codex_switch.auth import login, login_status, logout
from codex_switch.auth import LoginBootstrapAbortedError, ensure_instance_logged_in
from codex_switch.models import AppConfig
from codex_switch.models import InstanceConfig


def _make_launcher(tmp_path: Path, fake_codex_path: Path) -> Path:
    launcher = tmp_path / "codex"
    launcher.write_text(
        "#!/bin/sh\n"
        f'exec "{sys.executable}" "{fake_codex_path}" "$@"\n'
    )
    os.chmod(launcher, 0o755)
    return launcher


def _make_instance(tmp_path: Path) -> InstanceConfig:
    home = tmp_path / "instances" / "acct-001" / "home"
    home.mkdir(parents=True)
    return InstanceConfig(name="acct-001", order=1, home_dir=str(home))


def test_login_status_login_and_logout_round_trip(
    tmp_path, fake_codex_path: Path
) -> None:
    launcher = _make_launcher(tmp_path, fake_codex_path)
    instance = _make_instance(tmp_path)

    initial_status = login_status(launcher, instance)
    assert initial_status.logged_in is False
    assert initial_status.returncode == 1
    assert "Not logged in" in initial_status.output

    login(launcher, instance)

    logged_in_status = login_status(launcher, instance)
    assert logged_in_status.logged_in is True
    assert logged_in_status.returncode == 0
    assert "Logged in using ChatGPT" in logged_in_status.output

    logout(launcher, instance)

    final_status = login_status(launcher, instance)
    assert final_status.logged_in is False
    assert final_status.returncode == 1
    assert "Not logged in" in final_status.output


def test_ensure_instance_logged_in_allows_retry_skip_and_abort(
    tmp_path, monkeypatch
) -> None:
    instance = _make_instance(tmp_path)
    real_codex_path = tmp_path / "codex"
    real_codex_path.write_text("#!/bin/sh\n")
    real_codex_path.chmod(0o755)

    login_calls = {"count": 0}
    status_calls = {"count": 0}

    def fake_login(*args, **kwargs):
        login_calls["count"] += 1

    def fake_status(*args, **kwargs):
        status_calls["count"] += 1
        if status_calls["count"] < 3:
            return type("Status", (), {"logged_in": False, "output": "Not logged in", "returncode": 1})()
        return type("Status", (), {"logged_in": True, "output": "Logged in using ChatGPT", "returncode": 0})()

    monkeypatch.setattr("codex_switch.auth.login", fake_login)
    monkeypatch.setattr("codex_switch.auth.login_status", fake_status)

    responses = iter(["retry", "retry"])
    assert ensure_instance_logged_in(
        real_codex_path,
        instance,
        allow_skip=True,
        input_fn=lambda prompt="": next(responses),
        output_fn=lambda message: None,
    ) is True
    assert login_calls["count"] == 2

    monkeypatch.setattr("codex_switch.auth.login_status", lambda *args, **kwargs: type("Status", (), {"logged_in": False, "output": "Not logged in", "returncode": 1})())
    responses = iter(["skip"])
    assert ensure_instance_logged_in(
        real_codex_path,
        instance,
        allow_skip=True,
        input_fn=lambda prompt="": next(responses),
        output_fn=lambda message: None,
    ) is False

    responses = iter(["abort"])
    try:
        ensure_instance_logged_in(
            real_codex_path,
            instance,
            allow_skip=False,
            input_fn=lambda prompt="": next(responses),
            output_fn=lambda message: None,
        )
    except LoginBootstrapAbortedError:
        pass
    else:
        raise AssertionError("ensure_instance_logged_in should abort when requested")


def test_cli_login_and_logout_drive_upstream_commands(
    tmp_path, monkeypatch, fake_codex_path: Path
) -> None:
    monkeypatch.setenv("CODEX_SWITCH_HOME", str(tmp_path))
    launcher = _make_launcher(tmp_path, fake_codex_path)
    instance = _make_instance(tmp_path)

    save_config(
        AppConfig(
            real_codex_path=str(launcher),
            instances=[instance],
        )
    )

    runner = CliRunner()
    login_result = runner.invoke(app, ["login", "acct-001"])
    assert login_result.exit_code == 0
    assert "Logged in acct-001" in login_result.output

    logout_result = runner.invoke(app, ["logout", "acct-001"])
    assert logout_result.exit_code == 0
    assert "Logged out acct-001" in logout_result.output
