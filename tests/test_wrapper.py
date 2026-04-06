import json
from pathlib import Path

import pytest

from codex_switch.config import save_config
from codex_switch.models import AppConfig, InstanceConfig
from codex_switch.wrapper import main


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


def test_wrapper_reports_missing_config(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("CODEX_SWITCH_HOME", str(tmp_path))

    exit_code = main(["review"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "Codex Switch is not initialized" in captured.err


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
