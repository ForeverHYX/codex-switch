from __future__ import annotations

import re
import subprocess
from pathlib import Path

from codex_switch.models import InstanceConfig, ProbeResult
from codex_switch.runtime import build_instance_env


QUOTA_PATTERNS = (
    re.compile(r"remaining[^0-9]*(\d+)", re.IGNORECASE),
    re.compile(r"(\d+)[^0-9]*remaining", re.IGNORECASE),
)


def parse_remaining_quota(output: str) -> int:
    for pattern in QUOTA_PATTERNS:
        match = pattern.search(output)
        if match:
            return int(match.group(1))
    raise ValueError("Unable to parse remaining quota from /status output")


def _failure(instance: InstanceConfig, reason: str) -> ProbeResult:
    return ProbeResult(
        instance_name=instance.name,
        order=instance.order,
        quota_remaining=None,
        ok=False,
        reason=reason,
    )


def probe_instance(real_codex_path: str, instance: InstanceConfig) -> ProbeResult:
    env = build_instance_env(instance.name, Path(instance.home_dir))
    try:
        completed = subprocess.run(
            [real_codex_path, "--no-alt-screen"],
            input="/status\n/exit\n",
            text=True,
            capture_output=True,
            env=env,
            check=False,
            timeout=15,
        )
    except FileNotFoundError as exc:
        return _failure(instance, f"Probe could not launch the real Codex binary: {exc}")
    except subprocess.TimeoutExpired:
        return _failure(instance, "Probe timed out")

    output = f"{completed.stdout}\n{completed.stderr}"
    if completed.returncode != 0:
        return _failure(
            instance,
            f"Probe exited with exit code {completed.returncode}",
        )

    try:
        remaining = parse_remaining_quota(output)
    except ValueError as exc:
        return _failure(instance, str(exc))

    return ProbeResult(
        instance_name=instance.name,
        order=instance.order,
        quota_remaining=remaining,
        ok=True,
    )
