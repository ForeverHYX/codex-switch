import json
import os
import sys
from pathlib import Path

from codex_switch.config import save_config
from codex_switch.models import AppConfig, InstanceConfig
from codex_switch.wrapper import main


def test_wrapper_selects_highest_quota_instance_end_to_end(
    tmp_path,
    monkeypatch,
    fake_codex_path: Path,
) -> None:
    monkeypatch.setenv("CODEX_SWITCH_HOME", str(tmp_path))
    forwarded = tmp_path / "forwarded.json"
    monkeypatch.setenv("CODEX_SWITCH_FORWARD_OUTPUT", str(forwarded))

    launcher = tmp_path / "fake-codex"
    launcher.write_text(
        "#!/bin/sh\n"
        f'exec "{sys.executable}" "{fake_codex_path}" "$@"\n'
    )
    os.chmod(launcher, 0o755)

    acct1 = tmp_path / "instances" / "acct-001" / "home"
    acct2 = tmp_path / "instances" / "acct-002" / "home"
    acct1.mkdir(parents=True)
    acct2.mkdir(parents=True)
    (acct1 / "quota.txt").write_text("8")
    (acct2 / "quota.txt").write_text("17")

    save_config(
        AppConfig(
            real_codex_path=str(launcher),
            instances=[
                InstanceConfig(name="acct-001", order=1, home_dir=str(acct1)),
                InstanceConfig(name="acct-002", order=2, home_dir=str(acct2)),
            ],
        )
    )

    assert main(["review", "--json"]) == 0
    payload = json.loads(forwarded.read_text())
    assert payload["instance"] == "acct-002"
    assert payload["argv"] == ["review", "--json"]
