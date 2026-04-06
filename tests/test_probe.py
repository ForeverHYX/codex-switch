import subprocess

from codex_switch.models import InstanceConfig
from codex_switch.probe import parse_remaining_quota
from codex_switch.probe import probe_instance


def test_parse_remaining_quota_from_status_output() -> None:
    output = """
    Account: acct-001
    Requests remaining: 42
    """

    assert parse_remaining_quota(output) == 42


def test_probe_instance_returns_failure_for_malformed_output(
    tmp_path, monkeypatch
) -> None:
    instance = InstanceConfig(
        name="acct-001",
        order=1,
        home_dir=str(tmp_path / "home"),
    )

    monkeypatch.setattr(
        "codex_switch.probe.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args=["codex"],
            returncode=0,
            stdout="Account: acct-001\n",
            stderr="",
        ),
    )

    result = probe_instance("/usr/local/bin/codex", instance)

    assert result.ok is False
    assert result.quota_remaining is None
    assert "Unable to parse remaining quota" in result.reason


def test_probe_instance_returns_failure_for_nonzero_exit(
    tmp_path, monkeypatch
) -> None:
    instance = InstanceConfig(
        name="acct-001",
        order=1,
        home_dir=str(tmp_path / "home"),
    )

    monkeypatch.setattr(
        "codex_switch.probe.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args=["codex"],
            returncode=1,
            stdout="Requests remaining: 42\n",
            stderr="permission denied",
        ),
    )

    result = probe_instance("/usr/local/bin/codex", instance)

    assert result.ok is False
    assert result.quota_remaining is None
    assert "exit code 1" in result.reason


def test_probe_instance_returns_failure_for_timeout(tmp_path, monkeypatch) -> None:
    instance = InstanceConfig(
        name="acct-001",
        order=1,
        home_dir=str(tmp_path / "home"),
    )

    def raise_timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=["codex"], timeout=15)

    monkeypatch.setattr("codex_switch.probe.subprocess.run", raise_timeout)

    result = probe_instance("/usr/local/bin/codex", instance)

    assert result.ok is False
    assert result.quota_remaining is None
    assert result.reason == "Probe timed out"
