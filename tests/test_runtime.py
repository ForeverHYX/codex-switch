from pathlib import Path

from codex_switch.runtime import build_instance_env, find_real_codex, resolve_real_codex


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


def test_resolve_real_codex_prefers_existing_stored_path(tmp_path) -> None:
    stored = tmp_path / "codex"
    stored.write_text("#!/bin/sh\n")
    stored.chmod(0o755)

    assert resolve_real_codex(str(stored), tmp_path / "shim") == stored


def test_resolve_real_codex_recovers_when_stored_path_is_stale(
    tmp_path, monkeypatch
) -> None:
    wrapper_bin = tmp_path / "wrapper" / "bin"
    real_bin = tmp_path / "real" / "bin"
    wrapper_bin.mkdir(parents=True)
    real_bin.mkdir(parents=True)
    (real_bin / "codex").write_text("#!/bin/sh\n")
    (real_bin / "codex").chmod(0o755)
    monkeypatch.setenv("PATH", f"{wrapper_bin}:{real_bin}")

    assert resolve_real_codex(str(tmp_path / "missing" / "codex"), wrapper_bin) == real_bin / "codex"


def test_build_instance_env_sets_isolated_directories(tmp_path) -> None:
    env = build_instance_env(
        instance_name="acct-001",
        instance_home=tmp_path / "instances" / "acct-001" / "home",
        parent_env={"PATH": "/usr/bin"},
    )

    assert env["HOME"].endswith("acct-001/home")
    assert env["XDG_CONFIG_HOME"].endswith("acct-001/home/.config")
    assert env["CODEX_SWITCH_ACTIVE_INSTANCE"] == "acct-001"


def test_build_instance_env_with_empty_parent_env_does_not_inherit_process_env(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("PATH", "/inherited/bin")

    env = build_instance_env(
        instance_name="acct-002",
        instance_home=tmp_path / "instances" / "acct-002" / "home",
        parent_env={},
    )

    assert env["HOME"].endswith("acct-002/home")
    assert env["CODEX_SWITCH_ACTIVE_INSTANCE"] == "acct-002"
    assert env.get("PATH") is None
