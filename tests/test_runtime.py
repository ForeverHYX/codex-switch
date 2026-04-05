from pathlib import Path

from codex_switch.runtime import build_instance_env, find_real_codex


def test_find_real_codex_skips_wrapper_directory(tmp_path, monkeypatch) -> None:
    wrapper_bin = tmp_path / "wrapper" / "bin"
    real_bin = tmp_path / "real" / "bin"
    wrapper_bin.mkdir(parents=True)
    real_bin.mkdir(parents=True)
    (wrapper_bin / "codex").write_text("#!/bin/sh\n")
    (real_bin / "codex").write_text("#!/bin/sh\n")
    (wrapper_bin / "codex").chmod(0o755)
    (real_bin / "codex").chmod(0o755)
    monkeypatch.setenv("PATH", f"{wrapper_bin}:{real_bin}")

    assert find_real_codex(wrapper_bin) == real_bin / "codex"


def test_build_instance_env_sets_isolated_directories(tmp_path) -> None:
    env = build_instance_env(
        instance_name="acct-001",
        instance_home=tmp_path / "instances" / "acct-001" / "home",
        parent_env={"PATH": "/usr/bin"},
    )

    assert env["HOME"].endswith("acct-001/home")
    assert env["XDG_CONFIG_HOME"].endswith("acct-001/home/.config")
    assert env["CODEX_SWITCH_ACTIVE_INSTANCE"] == "acct-001"
