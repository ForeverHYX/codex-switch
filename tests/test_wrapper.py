import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from codex_switch.config import save_config
from codex_switch.models import AppConfig, InstanceConfig
from codex_switch.wrapper import main


def _make_launcher(tmp_path: Path, fake_codex: Path) -> Path:
    launcher = tmp_path / "codex"
    launcher.write_text(
        "#!/bin/sh\n"
        f'exec "{sys.executable}" "{fake_codex}" "$@"\n'
    )
    os.chmod(launcher, 0o755)
    return launcher


def test_wrapper_forwards_original_args_to_best_instance(tmp_path, monkeypatch) -> None:
    fake_codex = tmp_path / "fake_codex.py"
    forwarded = tmp_path / "forwarded.json"
    fake_codex.write_text(
        "from pathlib import Path\n"
        "import json, os, sys\n"
        "payload = {'argv': sys.argv[1:], 'instance': os.environ['CODEX_SWITCH_ACTIVE_INSTANCE']}\n"
        f"Path({str(forwarded)!r}).write_text(json.dumps(payload))\n"
    )
    monkeypatch.setenv("CODEX_SWITCH_HOME", str(tmp_path))

    save_config(
        AppConfig(
            real_codex_path="/usr/bin/python3",
            instances=[
                InstanceConfig(name="acct-001", order=1, home_dir=str(tmp_path / "acct-001")),
                InstanceConfig(name="acct-002", order=2, home_dir=str(tmp_path / "acct-002")),
            ],
        )
    )

    monkeypatch.setattr(
        "codex_switch.wrapper.probe_all_instances",
        lambda config: [
            type("Result", (), {"instance_name": "acct-001", "order": 1, "quota_remaining": 12, "ok": True})(),
            type("Result", (), {"instance_name": "acct-002", "order": 2, "quota_remaining": 21, "ok": True})(),
        ],
    )
    monkeypatch.setattr("codex_switch.wrapper.REAL_CODEX_ARGV", ["/usr/bin/python3", str(fake_codex)])

    exit_code = main(["review", "--json"])

    payload = json.loads(forwarded.read_text())
    assert exit_code == 0
    assert payload["argv"] == ["review", "--json"]
    assert payload["instance"] == "acct-002"


@pytest.mark.parametrize("command", ["login", "logout"])
def test_wrapper_blocks_managed_commands(command, capsys) -> None:
    exit_code = main([command, "acct-001"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "Use `codex-switch login` or `codex-switch logout` for account management" in captured.err


def test_wrapper_bootstraps_on_missing_config_and_resumes_command(
    tmp_path, monkeypatch, fake_codex_path: Path
) -> None:
    monkeypatch.setenv("CODEX_SWITCH_HOME", str(tmp_path))
    monkeypatch.setenv("CODEX_SWITCH_FORWARD_OUTPUT", str(tmp_path / "forwarded.json"))
    shared_home = tmp_path / "shared-home"
    (shared_home / ".codex" / "skills").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(shared_home))
    launcher = _make_launcher(tmp_path, fake_codex_path)
    monkeypatch.setenv("PATH", f"{tmp_path}:{os.environ['PATH']}")
    monkeypatch.setattr("builtins.input", lambda prompt="": "1")

    save_config_path = tmp_path / "config-should-not-exist-yet"
    assert not save_config_path.exists()

    exit_code = main(["review", "--json"])

    payload = json.loads((tmp_path / "forwarded.json").read_text())
    assert exit_code == 0
    assert payload["instance"] == "acct-001"
    assert payload["argv"] == ["review", "--json"]
    assert (tmp_path / "config.json").exists()
    assert launcher.exists()


def test_wrapper_reports_routing_failure(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("CODEX_SWITCH_HOME", str(tmp_path))

    save_config(
        AppConfig(
            real_codex_path="/usr/bin/python3",
            instances=[
                InstanceConfig(name="acct-001", order=1, home_dir=str(tmp_path / "acct-001"), enabled=False),
            ],
        )
    )

    exit_code = main(["review"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "No usable Codex account instances are available" in captured.err


def test_wrapper_reports_missing_real_codex_binary(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("CODEX_SWITCH_HOME", str(tmp_path))

    save_config(
        AppConfig(
            real_codex_path="/usr/bin/python3",
            instances=[
                InstanceConfig(name="acct-001", order=1, home_dir=str(tmp_path / "acct-001")),
            ],
        )
    )
    monkeypatch.setattr(
        "codex_switch.wrapper.probe_all_instances",
        lambda config: [
            type("Result", (), {"instance_name": "acct-001", "order": 1, "quota_remaining": 10, "ok": True})(),
        ],
    )
    monkeypatch.setattr(
        "codex_switch.wrapper.subprocess.run",
        lambda *args, **kwargs: (_ for _ in ()).throw(FileNotFoundError("missing codex")),
    )

    exit_code = main(["review"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "Unable to launch the real Codex binary" in captured.err


def test_wrapper_reports_missing_selected_instance(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("CODEX_SWITCH_HOME", str(tmp_path))

    save_config(
        AppConfig(
            real_codex_path="/usr/bin/python3",
            instances=[
                InstanceConfig(name="acct-001", order=1, home_dir=str(tmp_path / "acct-001")),
            ],
        )
    )
    monkeypatch.setattr(
        "codex_switch.wrapper.probe_all_instances",
        lambda config: [
            type("Result", (), {"instance_name": "acct-999", "order": 1, "quota_remaining": 10, "ok": True})(),
        ],
    )

    exit_code = main(["review"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "Selected instance 'acct-999' is not present in the config" in captured.err


def test_wrapper_recovers_stale_real_codex_path(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("CODEX_SWITCH_HOME", str(tmp_path))

    stale_path = tmp_path / "missing" / "codex"
    recovered_path = tmp_path / "real" / "codex"
    active_shim_dir = tmp_path / "shim" / "bin"
    recovered_path.parent.mkdir(parents=True)
    recovered_path.write_text("#!/bin/sh\n")
    recovered_path.chmod(0o755)

    save_config(
        AppConfig(
            real_codex_path=str(stale_path),
            instances=[
                InstanceConfig(name="acct-001", order=1, home_dir=str(tmp_path / "acct-001")),
            ],
        )
    )

    seen = {}

    def fake_resolve_real_codex(stored_path, wrapper_dir):
        assert stored_path == str(stale_path)
        seen["wrapper_dir"] = wrapper_dir
        return recovered_path

    def fake_probe_all_instances(config):
        seen["probe_path"] = config.real_codex_path
        return [
            type("Result", (), {"instance_name": "acct-001", "order": 1, "quota_remaining": 10, "ok": True})(),
        ]

    def fake_run(command, **kwargs):
        seen["command"] = command
        return subprocess.CompletedProcess(args=command, returncode=0)

    monkeypatch.setattr("codex_switch.wrapper.resolve_real_codex", fake_resolve_real_codex)
    monkeypatch.setattr("codex_switch.wrapper.probe_all_instances", fake_probe_all_instances)
    monkeypatch.setattr("codex_switch.wrapper.subprocess.run", fake_run)
    monkeypatch.setattr("codex_switch.wrapper.runtime_wrapper_dir", lambda: active_shim_dir)

    exit_code = main(["review"])

    assert exit_code == 0
    assert seen["wrapper_dir"] == active_shim_dir
    assert seen["probe_path"] == str(recovered_path)
    assert seen["command"][0] == str(recovered_path)
