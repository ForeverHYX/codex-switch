from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from typer.testing import CliRunner

from codex_switch.cli import app
from codex_switch.models import AppConfig, InstanceConfig


def _make_launcher(tmp_path: Path, fake_codex: Path) -> Path:
    launcher = tmp_path / "codex"
    launcher.write_text(
        "#!/bin/sh\n"
        f'exec "{sys.executable}" "{fake_codex}" "$@"\n'
    )
    os.chmod(launcher, 0o755)
    return launcher


def test_read_rate_limits_returns_structured_windows(tmp_path, fake_codex_path: Path) -> None:
    from codex_switch.rate_limits import read_rate_limits

    launcher = _make_launcher(tmp_path, fake_codex_path)
    home = tmp_path / "acct-001"
    home.mkdir()
    (home / "rate-limits.json").write_text(
        json.dumps(
            {
                "rateLimits": {
                    "limitId": "codex",
                    "limitName": None,
                    "planType": "plus",
                    "primary": {
                        "usedPercent": 64,
                        "windowDurationMins": 300,
                        "resetsAt": 1_775_461_397,
                    },
                    "secondary": {
                        "usedPercent": 29,
                        "windowDurationMins": 10080,
                        "resetsAt": 1_776_001_304,
                    },
                }
            }
        )
    )
    instance = InstanceConfig(name="acct-001", order=1, home_dir=str(home))

    snapshot = read_rate_limits(str(launcher), instance)

    assert snapshot.plan_type == "plus"
    assert snapshot.primary is not None
    assert snapshot.primary.used_percent == 64
    assert snapshot.primary.window_duration_mins == 300
    assert snapshot.secondary is not None
    assert snapshot.secondary.used_percent == 29
    assert snapshot.secondary.window_duration_mins == 10080


def test_read_cached_rate_limits_returns_latest_session_snapshot(tmp_path) -> None:
    from codex_switch.rate_limits import read_cached_rate_limits

    home = tmp_path / "acct-001"
    older_dir = home / ".codex" / "sessions" / "2026" / "04" / "07"
    latest_dir = home / ".codex" / "sessions" / "2026" / "04" / "08"
    older_dir.mkdir(parents=True)
    latest_dir.mkdir(parents=True)

    (older_dir / "rollout-old.jsonl").write_text(
        "\n".join(
            [
                '{"timestamp":"2026-04-07T01:00:00Z","type":"event_msg","payload":{"type":"token_count","rate_limits":{"limit_id":"codex","plan_type":"plus","primary":{"used_percent":60,"window_minutes":300,"resets_at":1775500000},"secondary":{"used_percent":25,"window_minutes":10080,"resets_at":1776000000}}}}',
            ]
        )
    )
    (latest_dir / "rollout-new.jsonl").write_text(
        "\n".join(
            [
                '{"timestamp":"2026-04-08T02:00:00Z","type":"event_msg","payload":{"type":"token_count","rate_limits":{"limit_id":"codex","plan_type":"plus","primary":{"used_percent":17,"window_minutes":300,"resets_at":1775600000},"secondary":{"used_percent":9,"window_minutes":10080,"resets_at":1776200000}}}}',
            ]
        )
    )

    instance = InstanceConfig(name="acct-001", order=1, home_dir=str(home))

    snapshot = read_cached_rate_limits(instance)

    assert snapshot is not None
    assert snapshot.plan_type == "plus"
    assert snapshot.primary is not None
    assert snapshot.primary.used_percent == 17
    assert snapshot.secondary is not None
    assert snapshot.secondary.used_percent == 9


def test_read_instance_rate_limits_falls_back_to_cached_snapshot(tmp_path, monkeypatch) -> None:
    from codex_switch.auth import CodexCommandError
    from codex_switch.rate_limits import read_instance_rate_limits

    home = tmp_path / "acct-001"
    session_dir = home / ".codex" / "sessions" / "2026" / "04" / "08"
    session_dir.mkdir(parents=True)
    (session_dir / "rollout.jsonl").write_text(
        '{"timestamp":"2026-04-08T02:00:00Z","type":"event_msg","payload":{"type":"token_count","rate_limits":{"limit_id":"codex","plan_type":"plus","primary":{"used_percent":24,"window_minutes":300,"resets_at":1775600000},"secondary":{"used_percent":11,"window_minutes":10080,"resets_at":1776200000}}}}\n'
    )

    instance = InstanceConfig(name="acct-001", order=1, home_dir=str(home))
    monkeypatch.setattr(
        "codex_switch.rate_limits.read_rate_limits",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            CodexCommandError("Timed out while reading account rate limits")
        ),
    )

    result = read_instance_rate_limits("/usr/local/bin/codex", instance)

    assert result.ok is True
    assert result.snapshot is not None
    assert result.snapshot.primary is not None
    assert result.snapshot.primary.used_percent == 24
    assert "cached rate limits" in (result.reason or "").lower()


def test_list_command_displays_live_rate_limits(tmp_path, monkeypatch) -> None:
    from codex_switch.rate_limits import (
        InstanceRateLimitResult,
        RateLimitSnapshot,
        RateLimitWindow,
    )

    config = AppConfig(
        real_codex_path="/usr/local/bin/codex",
        instances=[
            InstanceConfig(name="acct-001", order=1, home_dir=str(tmp_path / "acct-001")),
            InstanceConfig(name="acct-002", order=2, home_dir=str(tmp_path / "acct-002")),
        ],
    )

    def fake_read(real_codex_path: str, instance: InstanceConfig) -> InstanceRateLimitResult:
        if instance.name == "acct-001":
            return InstanceRateLimitResult(
                instance_name=instance.name,
                ok=True,
                snapshot=RateLimitSnapshot(
                    limit_id="codex",
                    limit_name=None,
                    plan_type="plus",
                    primary=RateLimitWindow(
                        used_percent=64,
                        window_duration_mins=300,
                        resets_at=1_775_461_397,
                    ),
                    secondary=RateLimitWindow(
                        used_percent=29,
                        window_duration_mins=10080,
                        resets_at=1_776_001_304,
                    ),
                ),
            )
        return InstanceRateLimitResult(
            instance_name=instance.name,
            ok=False,
            reason="Not logged in",
        )

    monkeypatch.setattr("codex_switch.cli._load_initialized_config", lambda: config)
    monkeypatch.setattr(
        "codex_switch.cli._resolve_real_codex_for_management",
        lambda config: config.real_codex_path,
    )
    monkeypatch.setattr("codex_switch.cli.read_instance_rate_limits", fake_read)

    result = CliRunner().invoke(app, ["list"])

    assert result.exit_code == 0
    assert "INSTANCE" in result.stdout
    assert "5H REMAINING" in result.stdout
    assert "7D REMAINING" in result.stdout
    assert "acct-001" in result.stdout
    assert "36%" in result.stdout
    assert "71%" in result.stdout
    assert "acct-002" in result.stdout
    assert "unavailable" in result.stdout
