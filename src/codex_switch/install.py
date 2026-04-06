from __future__ import annotations

import os
import sys
from pathlib import Path

from codex_switch.paths import shim_dir


def shim_path() -> Path:
    return shim_dir() / "codex"


def install_shim() -> Path:
    target = shim_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        "#!/bin/sh\n"
        f'exec "{sys.executable}" -m codex_switch.wrapper "$@"\n'
    )
    os.chmod(target, 0o755)
    return target


def uninstall_shim() -> Path:
    target = shim_path()
    if target.exists():
        target.unlink()
    return target
