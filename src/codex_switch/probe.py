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


def probe_instance(real_codex_path: str, instance: InstanceConfig) -> ProbeResult:
    env = build_instance_env(instance.name, Path(instance.home_dir))
    completed = subprocess.run(
        [real_codex_path, "--no-alt-screen"],
        input="/status\n/exit\n",
        text=True,
        capture_output=True,
        env=env,
        check=False,
        timeout=15,
    )
    remaining = parse_remaining_quota(f"{completed.stdout}\n{completed.stderr}")
    return ProbeResult(
        instance_name=instance.name,
        order=instance.order,
        quota_remaining=remaining,
        ok=True,
    )
