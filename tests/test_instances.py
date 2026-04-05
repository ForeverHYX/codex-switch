from codex_switch.instances import ensure_shared_codex_paths


def test_ensure_shared_codex_paths_links_skills(tmp_path) -> None:
    shared_home = tmp_path / "shared"
    instance_home = tmp_path / "instance"
    (shared_home / ".codex" / "skills").mkdir(parents=True)
    (shared_home / ".codex" / "superpowers").mkdir(parents=True)

    ensure_shared_codex_paths(instance_home=instance_home, shared_home=shared_home)

    assert (instance_home / ".codex" / "skills").is_symlink()
    assert (instance_home / ".codex" / "superpowers").is_symlink()
