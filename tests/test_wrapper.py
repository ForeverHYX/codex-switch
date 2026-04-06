import json
from pathlib import Path

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
