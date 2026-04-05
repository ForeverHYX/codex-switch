from codex_switch.instances import ensure_shared_codex_paths


def test_ensure_shared_codex_paths_links_skills(tmp_path) -> None:
    shared_home = tmp_path / "shared"
    instance_home = tmp_path / "instance"
    (shared_home / ".codex" / "skills").mkdir(parents=True)
    (shared_home / ".codex" / "superpowers").mkdir(parents=True)

    ensure_shared_codex_paths(instance_home=instance_home, shared_home=shared_home)

    assert (instance_home / ".codex" / "skills").is_symlink()
    assert (instance_home / ".codex" / "superpowers").is_symlink()


def test_ensure_shared_codex_paths_repairs_broken_and_wrong_links(tmp_path) -> None:
    shared_home = tmp_path / "shared"
    wrong_home = tmp_path / "wrong"
    instance_home = tmp_path / "instance"
    (shared_home / ".codex" / "skills").mkdir(parents=True)
    (shared_home / ".codex" / "superpowers").mkdir(parents=True)
    (wrong_home / ".codex" / "skills").mkdir(parents=True)
    (wrong_home / ".codex" / "superpowers").mkdir(parents=True)
    (instance_home / ".codex").mkdir(parents=True)
    (instance_home / ".codex" / "skills").symlink_to(wrong_home / ".codex" / "skills")
    (instance_home / ".codex" / "superpowers").symlink_to(
        instance_home / ".codex" / "missing-superpowers"
    )

    ensure_shared_codex_paths(instance_home=instance_home, shared_home=shared_home)
    ensure_shared_codex_paths(instance_home=instance_home, shared_home=shared_home)

    assert (instance_home / ".codex" / "skills").is_symlink()
    assert (instance_home / ".codex" / "skills").resolve(strict=False) == (
        shared_home / ".codex" / "skills"
    )
    assert (instance_home / ".codex" / "superpowers").is_symlink()
    assert (instance_home / ".codex" / "superpowers").resolve(strict=False) == (
        shared_home / ".codex" / "superpowers"
    )
