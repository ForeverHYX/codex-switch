from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def _login_state_path(home: Path) -> Path:
    return home / ".codex" / "login-state.json"


def _is_logged_in(home: Path) -> bool:
    return _login_state_path(home).exists()


def _set_logged_in(home: Path) -> None:
    state_path = _login_state_path(home)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps({"provider": "ChatGPT"}))


def _clear_logged_in(home: Path) -> None:
    state_path = _login_state_path(home)
    if state_path.exists():
        state_path.unlink()


def _handle_login_status(home: Path) -> int:
    if _is_logged_in(home):
        print("Logged in using ChatGPT")
        return 0
    print("Not logged in")
    return 1


def main() -> int:
    instance = os.environ["CODEX_SWITCH_ACTIVE_INSTANCE"]
    home = Path(os.environ["HOME"])
    argv = sys.argv[1:]

    if argv[:2] == ["login", "status"]:
        return _handle_login_status(home)

    if argv[:1] == ["login"]:
        _set_logged_in(home)
        print("Logged in using ChatGPT")
        return 0

    if argv[:1] == ["logout"]:
        _clear_logged_in(home)
        return 0

    if sys.stdin.isatty():
        print("OpenAI Codex ready", flush=True)
        for raw_line in sys.stdin:
            line = raw_line.strip()
            if line == "/status":
                quota_path = home / "quota.txt"
                quota = quota_path.read_text().strip() if quota_path.exists() else "1"
                print(f"Requests remaining: {quota}", flush=True)
            elif line == "/exit":
                return 0
        return 0

    stdin_payload = sys.stdin.read()
    if "/status" in stdin_payload:
        quota_path = home / "quota.txt"
        quota = quota_path.read_text().strip() if quota_path.exists() else "1"
        print(f"Requests remaining: {quota}")
        return 0

    payload = {"argv": argv, "instance": instance}
    output_path = os.environ.get("CODEX_SWITCH_FORWARD_OUTPUT")
    if output_path:
        Path(output_path).write_text(json.dumps(payload))
    else:
        print(json.dumps(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
