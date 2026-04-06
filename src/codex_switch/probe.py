from __future__ import annotations

import os
import pty
import re
import select
import subprocess
import time
from pathlib import Path

from codex_switch.auth import CodexCommandError, login_status
from codex_switch.models import InstanceConfig, ProbeResult
from codex_switch.runtime import build_instance_env


QUOTA_PATTERNS = (
    re.compile(r"remaining[^0-9]*(\d+)", re.IGNORECASE),
    re.compile(r"(\d+)[^0-9]*remaining", re.IGNORECASE),
)
READY_PATTERNS = (
    "OpenAI Codex",
    "tab to queue message",
    "context left",
    "Codex ready",
    "BOOTED",
)
ANSI_ESCAPE_RE = re.compile(
    r"\x1b\[[0-?]*[ -/]*[@-~]|\x1b\][^\x07]*(?:\x07|\x1b\\)|\x1b[@-_]"
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


def _sanitize_terminal_output(raw_output: bytes) -> str:
    text = raw_output.decode("utf-8", errors="ignore").replace("\r", "\n")
    text = ANSI_ESCAPE_RE.sub("", text)
    text = text.replace("\b", "")
    return text


def _trusted_project_override(path: Path) -> str:
    escaped = str(path).replace("\\", "\\\\").replace('"', '\\"')
    return f'projects."{escaped}".trust_level="trusted"'


def _looks_ready(output: str) -> bool:
    return any(pattern in output for pattern in READY_PATTERNS)


def _fallback_logged_in_result(
    real_codex_path: str,
    instance: InstanceConfig,
    reason: str,
) -> ProbeResult | None:
    try:
        status = login_status(real_codex_path, instance)
    except CodexCommandError:
        return None
    if not status.logged_in:
        return None
    return ProbeResult(
        instance_name=instance.name,
        order=instance.order,
        quota_remaining=0,
        ok=True,
        reason=f"{reason}. Falling back to login-only availability.",
    )


def _run_status_probe(
    real_codex_path: str,
    instance: InstanceConfig,
    *,
    timeout: int = 6,
) -> tuple[int, str]:
    instance_home = Path(instance.home_dir)
    instance_home.mkdir(parents=True, exist_ok=True)
    env = build_instance_env(instance.name, instance_home)
    command = [
        real_codex_path,
        "-C",
        str(instance_home),
        "-c",
        _trusted_project_override(instance_home),
        "--no-alt-screen",
    ]

    master_fd, slave_fd = pty.openpty()
    process: subprocess.Popen[bytes] | None = None
    sent_status = False
    sent_exit = False
    sent_trust = False
    status_sent_at: float | None = None
    exit_sent_at: float | None = None
    output = bytearray()
    deadline = time.monotonic() + timeout
    startup_deadline = time.monotonic() + min(3.0, timeout / 2)

    try:
        process = subprocess.Popen(
            command,
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            env=env,
            cwd=instance_home,
            close_fds=True,
        )
    finally:
        os.close(slave_fd)

    try:
        while True:
            now = time.monotonic()
            if now >= deadline:
                raise subprocess.TimeoutExpired(cmd=command, timeout=timeout)

            wait_for = min(0.2, deadline - now)
            ready, _, _ = select.select([master_fd], [], [], wait_for)
            if ready:
                try:
                    chunk = os.read(master_fd, 4096)
                except OSError:
                    chunk = b""
                if chunk:
                    output.extend(chunk)

            cleaned_output = _sanitize_terminal_output(output)

            if (
                not sent_trust
                and "Do you trust the contents of this directory?" in cleaned_output
            ):
                os.write(master_fd, b"1\n")
                sent_trust = True

            if not sent_status and (
                _looks_ready(cleaned_output) or time.monotonic() >= startup_deadline
            ):
                os.write(master_fd, b"/status\n")
                sent_status = True
                status_sent_at = time.monotonic()

            if sent_status and not sent_exit:
                try:
                    parse_remaining_quota(cleaned_output)
                except ValueError:
                    if status_sent_at is not None and time.monotonic() - status_sent_at > 2:
                        os.write(master_fd, b"/exit\n")
                        sent_exit = True
                        exit_sent_at = time.monotonic()
                else:
                    os.write(master_fd, b"/exit\n")
                    sent_exit = True
                    exit_sent_at = time.monotonic()

            if (
                sent_exit
                and exit_sent_at is not None
                and time.monotonic() - exit_sent_at > 1
                and process.poll() is None
            ):
                process.terminate()

            poll_result = process.poll()
            if poll_result is not None:
                while True:
                    ready, _, _ = select.select([master_fd], [], [], 0)
                    if not ready:
                        break
                    try:
                        chunk = os.read(master_fd, 4096)
                    except OSError:
                        break
                    if not chunk:
                        break
                    output.extend(chunk)
                return poll_result, _sanitize_terminal_output(output)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=1)
        raise
    finally:
        os.close(master_fd)


def probe_instance(real_codex_path: str, instance: InstanceConfig) -> ProbeResult:
    try:
        returncode, output = _run_status_probe(real_codex_path, instance)
    except FileNotFoundError as exc:
        return _failure(instance, f"Probe could not launch the real Codex binary: {exc}")
    except subprocess.TimeoutExpired:
        fallback = _fallback_logged_in_result(
            real_codex_path,
            instance,
            "Probe timed out",
        )
        if fallback is not None:
            return fallback
        return _failure(instance, "Probe timed out")

    if returncode != 0:
        fallback = _fallback_logged_in_result(
            real_codex_path,
            instance,
            f"Probe exited with exit code {returncode}",
        )
        if fallback is not None:
            return fallback
        return _failure(instance, f"Probe exited with exit code {returncode}")

    try:
        remaining = parse_remaining_quota(output)
    except ValueError as exc:
        fallback = _fallback_logged_in_result(real_codex_path, instance, str(exc))
        if fallback is not None:
            return fallback
        return _failure(instance, str(exc))

    return ProbeResult(
        instance_name=instance.name,
        order=instance.order,
        quota_remaining=remaining,
        ok=True,
    )
