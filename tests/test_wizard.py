from pathlib import Path

from codex_switch.wizard import initialize_app


def test_initialize_app_creates_instances_and_config(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("CODEX_SWITCH_HOME", str(tmp_path))
    shared_home = tmp_path / "shared-home"
    (shared_home / ".codex" / "skills").mkdir(parents=True)

    config = initialize_app(
        real_codex_path=Path("/usr/local/bin/codex"),
        instance_count=2,
        shared_home=shared_home,
    )

    assert [instance.name for instance in config.instances] == ["acct-001", "acct-002"]
    assert (tmp_path / "instances" / "acct-001" / "home").exists()
    assert (tmp_path / "config.json").exists()
