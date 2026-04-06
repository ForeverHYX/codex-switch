from __future__ import annotations

import json
import select
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from codex_switch.auth import CodexCommandError
from codex_switch.models import InstanceConfig
from codex_switch.runtime import build_instance_env


INITIALIZE_REQUEST_ID = 1
RATE_LIMITS_REQUEST_ID = 2
FIVE_HOUR_WINDOW_MINS = 300
SEVEN_DAY_WINDOW_MINS = 10080


@dataclass(slots=True)
class RateLimitWindow:
    used_percent: int
    window_duration_mins: int | None = None
    resets_at: int | None = None

    @property
    def remaining_percent(self) -> int:
        return max(0, 100 - self.used_percent)


@dataclass(slots=True)
class RateLimitSnapshot:
    limit_id: str | None
    limit_name: str | None
    plan_type: str | None
    primary: RateLimitWindow | None = None
    secondary: RateLimitWindow | None = None


@dataclass(slots=True)
class InstanceRateLimitResult:
    instance_name: str
    ok: bool
    snapshot: RateLimitSnapshot | None = None
    reason: str | None = None


def _start_app_server(
    real_codex_path: str | Path,
    instance: InstanceConfig,
) -> subprocess.Popen[str]:
    instance_home = Path(instance.home_dir)
    instance_home.mkdir(parents=True, exist_ok=True)
    try:
        return subprocess.Popen(
            [str(real_codex_path), "app-server"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=build_instance_env(instance.name, instance_home),
            cwd=instance_home,
        )
    except FileNotFoundError as exc:
        raise CodexCommandError(f"Unable to launch the real Codex binary: {exc}") from exc


def _write_request(
    process: subprocess.Popen[str],
    request_id: int,
    method: str,
    params: object,
) -> None:
    if process.stdin is None:
        raise CodexCommandError("Codex app-server stdin is unavailable")
    process.stdin.write(
        json.dumps(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": method,
                "params": params,
            }
        )
        + "\n"
    )
    process.stdin.flush()


def _read_response(
    process: subprocess.Popen[str],
    request_id: int,
    *,
    timeout: float,
) -> dict[str, object]:
    if process.stdout is None:
        raise CodexCommandError("Codex app-server stdout is unavailable")

    deadline = time.monotonic() + timeout
    stdout_fd = process.stdout.fileno()

    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise subprocess.TimeoutExpired(cmd=process.args, timeout=timeout)

        ready, _, _ = select.select([stdout_fd], [], [], remaining)
        if not ready:
            raise subprocess.TimeoutExpired(cmd=process.args, timeout=timeout)

        line = process.stdout.readline()
        if not line:
            stderr_output = ""
            if process.stderr is not None:
                stderr_output = process.stderr.read().strip()
            message = "Codex app-server exited before returning a response"
            if stderr_output:
                message = f"{message}: {stderr_output}"
            raise CodexCommandError(message)

        payload = json.loads(line)
        if payload.get("id") != request_id:
            continue
        return payload


def _extract_result(payload: dict[str, object], method: str) -> dict[str, object]:
    error = payload.get("error")
    if isinstance(error, dict):
        message = error.get("message")
        if isinstance(message, str) and message:
            raise CodexCommandError(f"{method} failed: {message}")
        raise CodexCommandError(f"{method} failed")

    result = payload.get("result")
    if not isinstance(result, dict):
        raise CodexCommandError(f"{method} returned an invalid payload")
    return result


def _parse_window(payload: object) -> RateLimitWindow | None:
    if payload is None:
        return None
    if not isinstance(payload, dict):
        raise CodexCommandError("Rate limit window payload is malformed")

    used_percent = payload.get("usedPercent")
    if not isinstance(used_percent, int) or isinstance(used_percent, bool):
        raise CodexCommandError("Rate limit window is missing usedPercent")

    window_duration_mins = payload.get("windowDurationMins")
    if window_duration_mins is not None and (
        not isinstance(window_duration_mins, int) or isinstance(window_duration_mins, bool)
    ):
        raise CodexCommandError("Rate limit window has an invalid windowDurationMins")

    resets_at = payload.get("resetsAt")
    if resets_at is not None and (not isinstance(resets_at, int) or isinstance(resets_at, bool)):
        raise CodexCommandError("Rate limit window has an invalid resetsAt")

    return RateLimitWindow(
        used_percent=used_percent,
        window_duration_mins=window_duration_mins,
        resets_at=resets_at,
    )


def _parse_snapshot(payload: dict[str, object]) -> RateLimitSnapshot:
    return RateLimitSnapshot(
        limit_id=payload.get("limitId") if isinstance(payload.get("limitId"), str) else None,
        limit_name=payload.get("limitName") if isinstance(payload.get("limitName"), str) else None,
        plan_type=payload.get("planType") if isinstance(payload.get("planType"), str) else None,
        primary=_parse_window(payload.get("primary")),
        secondary=_parse_window(payload.get("secondary")),
    )


def _select_snapshot(result_payload: dict[str, object]) -> dict[str, object]:
    by_limit = result_payload.get("rateLimitsByLimitId")
    if isinstance(by_limit, dict):
        codex_snapshot = by_limit.get("codex")
        if isinstance(codex_snapshot, dict):
            return codex_snapshot

    rate_limits = result_payload.get("rateLimits")
    if isinstance(rate_limits, dict):
        return rate_limits

    raise CodexCommandError("account/rateLimits/read returned no rate limit snapshot")


def read_rate_limits(
    real_codex_path: str | Path,
    instance: InstanceConfig,
    *,
    timeout: float = 8,
) -> RateLimitSnapshot:
    process = _start_app_server(real_codex_path, instance)
    try:
        _write_request(
            process,
            INITIALIZE_REQUEST_ID,
            "initialize",
            {
                "clientInfo": {
                    "name": "codex-switch",
                    "version": "0.1.3",
                },
                "capabilities": {
                    "experimentalApi": True,
                },
            },
        )
        init_payload = _read_response(
            process, INITIALIZE_REQUEST_ID, timeout=max(1.0, timeout / 2)
        )
        _extract_result(init_payload, "initialize")

        _write_request(process, RATE_LIMITS_REQUEST_ID, "account/rateLimits/read", None)
        rate_limit_payload = _read_response(
            process, RATE_LIMITS_REQUEST_ID, timeout=max(1.0, timeout / 2)
        )
        result = _extract_result(rate_limit_payload, "account/rateLimits/read")
        return _parse_snapshot(_select_snapshot(result))
    except subprocess.TimeoutExpired as exc:
        raise CodexCommandError("Timed out while reading account rate limits") from exc
    finally:
        if process.stdin is not None and not process.stdin.closed:
            process.stdin.close()
        try:
            process.terminate()
            process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=1)


def read_instance_rate_limits(
    real_codex_path: str | Path,
    instance: InstanceConfig,
) -> InstanceRateLimitResult:
    try:
        snapshot = read_rate_limits(real_codex_path, instance)
    except CodexCommandError as exc:
        return InstanceRateLimitResult(
            instance_name=instance.name,
            ok=False,
            reason=str(exc),
        )
    return InstanceRateLimitResult(
        instance_name=instance.name,
        ok=True,
        snapshot=snapshot,
    )


def select_window_for_duration(
    snapshot: RateLimitSnapshot,
    duration_mins: int,
    *,
    fallback: str | None = None,
) -> RateLimitWindow | None:
    candidates = [snapshot.primary, snapshot.secondary]
    for window in candidates:
        if window is not None and window.window_duration_mins == duration_mins:
            return window

    if fallback == "primary":
        return snapshot.primary
    if fallback == "secondary":
        return snapshot.secondary
    return None


def format_reset_timestamp(timestamp: int | None) -> str:
    if timestamp is None:
        return "-"
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M")
