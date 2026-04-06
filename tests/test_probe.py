import subprocess
import os
import sys
from pathlib import Path

from codex_switch.models import InstanceConfig
from codex_switch.auth import LoginStatus
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
        "codex_switch.probe._run_status_probe",
        lambda *args, **kwargs: (0, "Account: acct-001\n"),
    )
    monkeypatch.setattr(
        "codex_switch.probe.login_status",
        lambda *args, **kwargs: LoginStatus(logged_in=False, output="", returncode=1),
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
        "codex_switch.probe._run_status_probe",
        lambda *args, **kwargs: (1, "Requests remaining: 42\npermission denied"),
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

    monkeypatch.setattr("codex_switch.probe._run_status_probe", raise_timeout)

    result = probe_instance("/usr/local/bin/codex", instance)

    assert result.ok is False
    assert result.quota_remaining is None
    assert result.reason == "Probe timed out"


def test_probe_instance_handles_tty_only_codex_process(tmp_path) -> None:
    home_dir = tmp_path / "acct-home"
    home_dir.mkdir()
    instance = InstanceConfig(
        name="acct-001",
        order=1,
        home_dir=str(home_dir),
    )
    script_path = tmp_path / "fake_tty_codex.py"
    launcher_path = tmp_path / "fake-codex"
    script_path.write_text(
        "import os\n"
        "import sys\n"
        "print('OpenAI Codex ready', flush=True)\n"
        "if not sys.stdin.isatty():\n"
        "    print('stdin is not a terminal', file=sys.stderr, flush=True)\n"
        "    raise SystemExit(1)\n"
        "expected_cwd = os.environ.get('EXPECTED_CWD')\n"
        "if expected_cwd and os.getcwd() != expected_cwd:\n"
        "    print(f'bad cwd: {os.getcwd()}', file=sys.stderr, flush=True)\n"
        "    raise SystemExit(2)\n"
        "for raw_line in sys.stdin:\n"
        "    line = raw_line.strip()\n"
        "    if line == '/status':\n"
        "        print('Requests remaining: 42', flush=True)\n"
        "    elif line == '/exit':\n"
        "        raise SystemExit(0)\n"
    )
    launcher_path.write_text(
        "#!/bin/sh\n"
        f'exec "{sys.executable}" "{script_path}" "$@"\n'
    )
    os.chmod(launcher_path, 0o755)

    previous_expected_cwd = os.environ.get("EXPECTED_CWD")
    os.environ["EXPECTED_CWD"] = str(home_dir)
    try:
        result = probe_instance(str(launcher_path), instance)
    finally:
        if previous_expected_cwd is None:
            os.environ.pop("EXPECTED_CWD", None)
        else:
            os.environ["EXPECTED_CWD"] = previous_expected_cwd

    assert result.ok is True
    assert result.quota_remaining == 42


def test_probe_instance_falls_back_to_logged_in_account_when_quota_parse_fails(
    tmp_path, monkeypatch
) -> None:
    instance = InstanceConfig(
        name="acct-001",
        order=1,
        home_dir=str(tmp_path / "home"),
    )

    monkeypatch.setattr(
        "codex_switch.probe._run_status_probe",
        lambda *args, **kwargs: (0, "Account status unavailable\n"),
    )
    monkeypatch.setattr(
        "codex_switch.probe.login_status",
        lambda *args, **kwargs: LoginStatus(
            logged_in=True,
            output="Logged in using ChatGPT",
            returncode=0,
        ),
    )

    result = probe_instance("/usr/local/bin/codex", instance)

    assert result.ok is True
    assert result.quota_remaining == 0
    assert "falling back" in (result.reason or "").lower()
