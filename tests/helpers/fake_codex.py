from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def main() -> int:
    instance = os.environ["CODEX_SWITCH_ACTIVE_INSTANCE"]
    home = Path(os.environ["HOME"])
    stdin_payload = sys.stdin.read()

    if "/status" in stdin_payload:
        quota = (home / "quota.txt").read_text().strip()
        print(f"Requests remaining: {quota}")
        return 0

    payload = {"argv": sys.argv[1:], "instance": instance}
    output_path = os.environ.get("CODEX_SWITCH_FORWARD_OUTPUT")
    if output_path:
        Path(output_path).write_text(json.dumps(payload))
    else:
        print(json.dumps(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
