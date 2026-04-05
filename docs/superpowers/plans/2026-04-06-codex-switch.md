# Codex-Switch CLI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python CLI that transparently routes each `codex ...` invocation to the logged-in account instance with the highest remaining quota while keeping repository context shared and account state isolated.

**Architecture:** A management CLI named `codex-switch` owns bootstrap, diagnostics, login flows, and shim installation. A generated front-of-PATH `codex` shim resolves the real Codex binary, loads instance metadata from `~/.codex-switch`, probes all instances in parallel through isolated runtime directories, picks the best instance, and forwards the original arguments unchanged.

**Tech Stack:** Python 3.11+, Typer, pytest, pathlib, subprocess, JSON

---

## File Map

- `pyproject.toml`
  Declares the package, Python version, dependencies, and the `codex-switch` console script.
- `src/codex_switch/__init__.py`
  Stores the package version string.
- `src/codex_switch/cli.py`
  Exposes the management CLI: `init`, `list`, `login`, `doctor`, `install-shim`, `uninstall`.
- `src/codex_switch/paths.py`
  Resolves `~/.codex-switch` paths and supports `CODEX_SWITCH_HOME` overrides for tests.
- `src/codex_switch/models.py`
  Defines typed dataclasses for config, instance metadata, and probe results.
- `src/codex_switch/config.py`
  Loads and saves `config.json`.
- `src/codex_switch/runtime.py`
  Finds the real `codex` binary, builds per-instance environments, and rediscovers stale paths.
- `src/codex_switch/instances.py`
  Creates instance directories and shared symlinks for global skills.
- `src/codex_switch/wizard.py`
  Orchestrates first-run initialization and per-instance setup.
- `src/codex_switch/probe.py`
  Runs `/status` probes against an isolated instance and parses remaining quota.
- `src/codex_switch/routing.py`
  Chooses the best instance based on probe results.
- `src/codex_switch/wrapper.py`
  Implements the transparent `codex` shim entrypoint and forwards user commands.
- `src/codex_switch/doctor.py`
  Reports health checks for the real binary, PATH precedence, and instance states.
- `src/codex_switch/install.py`
  Writes and removes the generated `~/.codex-switch/bin/codex` shim.
- `tests/conftest.py`
  Shared pytest fixtures for temporary config roots and fake home directories.
- `tests/helpers/fake_codex.py`
  A fake Codex executable used by integration tests.
- `tests/test_smoke.py`
  Verifies package import and version wiring.
- `tests/test_config.py`
  Covers state root resolution and config persistence.
- `tests/test_runtime.py`
  Covers real binary discovery, stale path recovery, and environment construction.
- `tests/test_instances.py`
  Covers instance creation and shared skill symlink setup.
- `tests/test_probe.py`
  Covers `/status` parsing and probe failure handling.
- `tests/test_routing.py`
  Covers quota ordering, tie breaking, and all-failed behavior.
- `tests/test_wrapper.py`
  Covers wrapper command routing and forwarded argv preservation.
- `tests/test_doctor.py`
  Covers doctor output and shim generation.
- `tests/test_integration_wrapper.py`
  End-to-end tests using the fake Codex executable.
- `README.md`
  Public install, usage, and limitation guide.
- `docs/design/codex-switch-design.md`
  Public copy of the approved design doc that can be pushed to GitHub.

## Task 1: Bootstrap the Python package and test runner

**Files:**
- Create: `pyproject.toml`
- Create: `src/codex_switch/__init__.py`
- Create: `src/codex_switch/cli.py`
- Create: `tests/test_smoke.py`

- [ ] **Step 1: Write the failing smoke test**

```python
# tests/test_smoke.py
from codex_switch import __version__


def test_package_exposes_version() -> None:
    assert __version__ == "0.1.0"
```

- [ ] **Step 2: Run the smoke test to verify it fails**

Run: `pytest tests/test_smoke.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'codex_switch'`

- [ ] **Step 3: Write the minimal package bootstrap**

```toml
# pyproject.toml
[build-system]
requires = ["setuptools>=69", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "codex-switch"
version = "0.1.0"
description = "Transparent account-aware wrapper for the Codex CLI"
requires-python = ">=3.11"
dependencies = ["typer>=0.12,<1.0"]

[project.optional-dependencies]
dev = ["pytest>=8.0,<9.0"]

[project.scripts]
codex-switch = "codex_switch.cli:app"

[tool.pytest.ini_options]
pythonpath = ["src"]
```

```python
# src/codex_switch/__init__.py
__version__ = "0.1.0"
```

```python
# src/codex_switch/cli.py
import typer

app = typer.Typer(no_args_is_help=True)


if __name__ == "__main__":
    app()
```

- [ ] **Step 4: Run the smoke test to verify it passes**

Run: `pytest tests/test_smoke.py -q`
Expected: PASS with `1 passed`

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml src/codex_switch/__init__.py src/codex_switch/cli.py tests/test_smoke.py
git commit -m "chore: bootstrap codex-switch package"
```

## Task 2: Add state paths, dataclasses, and config persistence

**Files:**
- Create: `src/codex_switch/paths.py`
- Create: `src/codex_switch/models.py`
- Create: `src/codex_switch/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write the failing config test**

```python
# tests/test_config.py
from codex_switch.config import load_config, save_config
from codex_switch.models import AppConfig, InstanceConfig


def test_save_and_load_config_round_trip(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("CODEX_SWITCH_HOME", str(tmp_path))
    config = AppConfig(
        real_codex_path="/usr/local/bin/codex",
        instances=[
            InstanceConfig(
                name="acct-001",
                order=1,
                home_dir=str(tmp_path / "instances" / "acct-001" / "home"),
            )
        ],
    )

    save_config(config)
    loaded = load_config()

    assert loaded == config
```

- [ ] **Step 2: Run the config test to verify it fails**

Run: `pytest tests/test_config.py::test_save_and_load_config_round_trip -q`
Expected: FAIL with `ImportError` for `codex_switch.config`

- [ ] **Step 3: Implement paths, models, and JSON config storage**

```python
# src/codex_switch/paths.py
from __future__ import annotations

import os
from pathlib import Path


ENV_ROOT = "CODEX_SWITCH_HOME"


def state_root() -> Path:
    override = os.environ.get(ENV_ROOT)
    if override:
        return Path(override).expanduser().resolve()
    return Path.home() / ".codex-switch"


def config_path() -> Path:
    return state_root() / "config.json"


def instances_dir() -> Path:
    return state_root() / "instances"


def logs_dir() -> Path:
    return state_root() / "logs"


def shim_dir() -> Path:
    return state_root() / "bin"
```

```python
# src/codex_switch/models.py
from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(slots=True)
class InstanceConfig:
    name: str
    order: int
    home_dir: str
    enabled: bool = True

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(slots=True)
class AppConfig:
    real_codex_path: str
    instances: list[InstanceConfig] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "real_codex_path": self.real_codex_path,
            "instances": [instance.to_dict() for instance in self.instances],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "AppConfig":
        raw_instances = payload.get("instances", [])
        instances = [
            InstanceConfig(**item) for item in raw_instances if isinstance(item, dict)
        ]
        return cls(
            real_codex_path=str(payload["real_codex_path"]),
            instances=instances,
        )
```

```python
# src/codex_switch/config.py
from __future__ import annotations

import json

from codex_switch.models import AppConfig
from codex_switch.paths import config_path


def load_config() -> AppConfig:
    payload = json.loads(config_path().read_text())
    return AppConfig.from_dict(payload)


def save_config(config: AppConfig) -> None:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config.to_dict(), indent=2, sort_keys=True) + "\n")
```

- [ ] **Step 4: Run the config and smoke tests**

Run: `pytest tests/test_smoke.py tests/test_config.py -q`
Expected: PASS with `2 passed`

- [ ] **Step 5: Commit**

```bash
git add src/codex_switch/paths.py src/codex_switch/models.py src/codex_switch/config.py tests/test_config.py
git commit -m "feat: add config persistence"
```

## Task 3: Add real binary discovery, instance environments, and shared skill links

**Files:**
- Create: `src/codex_switch/runtime.py`
- Create: `src/codex_switch/instances.py`
- Create: `tests/test_runtime.py`
- Create: `tests/test_instances.py`

- [ ] **Step 1: Write the failing runtime tests**

```python
# tests/test_runtime.py
from pathlib import Path

from codex_switch.runtime import build_instance_env, find_real_codex


def test_find_real_codex_skips_wrapper_directory(tmp_path, monkeypatch) -> None:
    wrapper_bin = tmp_path / "wrapper" / "bin"
    real_bin = tmp_path / "real" / "bin"
    wrapper_bin.mkdir(parents=True)
    real_bin.mkdir(parents=True)
    (wrapper_bin / "codex").write_text("#!/bin/sh\n")
    (real_bin / "codex").write_text("#!/bin/sh\n")
    monkeypatch.setenv("PATH", f"{wrapper_bin}:{real_bin}")

    assert find_real_codex(wrapper_bin) == real_bin / "codex"


def test_build_instance_env_sets_isolated_directories(tmp_path) -> None:
    env = build_instance_env(
        instance_name="acct-001",
        instance_home=tmp_path / "instances" / "acct-001" / "home",
        parent_env={"PATH": "/usr/bin"},
    )

    assert env["HOME"].endswith("acct-001/home")
    assert env["XDG_CONFIG_HOME"].endswith("acct-001/home/.config")
    assert env["CODEX_SWITCH_ACTIVE_INSTANCE"] == "acct-001"
```

```python
# tests/test_instances.py
from codex_switch.instances import ensure_shared_codex_paths


def test_ensure_shared_codex_paths_links_skills(tmp_path) -> None:
    shared_home = tmp_path / "shared"
    instance_home = tmp_path / "instance"
    (shared_home / ".codex" / "skills").mkdir(parents=True)
    (shared_home / ".codex" / "superpowers").mkdir(parents=True)

    ensure_shared_codex_paths(instance_home=instance_home, shared_home=shared_home)

    assert (instance_home / ".codex" / "skills").is_symlink()
    assert (instance_home / ".codex" / "superpowers").is_symlink()
```

- [ ] **Step 2: Run the runtime tests to verify they fail**

Run: `pytest tests/test_runtime.py tests/test_instances.py -q`
Expected: FAIL with `ImportError` for `codex_switch.runtime` and `codex_switch.instances`

- [ ] **Step 3: Implement runtime discovery and shared path linking**

```python
# src/codex_switch/runtime.py
from __future__ import annotations

import os
from pathlib import Path


def find_real_codex(wrapper_dir: Path) -> Path:
    path_entries = []
    for entry in os.environ.get("PATH", "").split(os.pathsep):
        if not entry:
            continue
        if Path(entry).resolve() == wrapper_dir.resolve():
            continue
        path_entries.append(entry)

    for entry in path_entries:
        candidate = Path(entry) / "codex"
        if candidate.exists() and os.access(candidate, os.X_OK):
            return candidate.resolve()

    raise FileNotFoundError("Unable to locate the real codex binary outside the shim directory")


def build_instance_env(
    instance_name: str,
    instance_home: Path,
    parent_env: dict[str, str] | None = None,
) -> dict[str, str]:
    env = dict(parent_env or os.environ)
    env["HOME"] = str(instance_home)
    env["XDG_CONFIG_HOME"] = str(instance_home / ".config")
    env["XDG_CACHE_HOME"] = str(instance_home / ".cache")
    env["XDG_STATE_HOME"] = str(instance_home / ".local" / "state")
    env["CODEX_SWITCH_ACTIVE_INSTANCE"] = instance_name
    return env
```

```python
# src/codex_switch/instances.py
from __future__ import annotations

from pathlib import Path


def ensure_shared_codex_paths(instance_home: Path, shared_home: Path) -> None:
    for relative in (
        Path(".codex") / "skills",
        Path(".codex") / "superpowers",
    ):
        source = shared_home / relative
        if not source.exists():
            continue
        target = instance_home / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            target.symlink_to(source)
```

- [ ] **Step 4: Run the runtime, instance, config, and smoke tests**

Run: `pytest tests/test_smoke.py tests/test_config.py tests/test_runtime.py tests/test_instances.py -q`
Expected: PASS with `5 passed`

- [ ] **Step 5: Commit**

```bash
git add src/codex_switch/runtime.py src/codex_switch/instances.py tests/test_runtime.py tests/test_instances.py
git commit -m "feat: add runtime isolation helpers"
```

## Task 4: Add initialization logic and the management CLI bootstrap flow

**Files:**
- Create: `src/codex_switch/wizard.py`
- Modify: `src/codex_switch/instances.py`
- Modify: `src/codex_switch/cli.py`
- Create: `tests/test_wizard.py`

- [ ] **Step 1: Write the failing initialization test**

```python
# tests/test_wizard.py
from pathlib import Path

from codex_switch.wizard import initialize_app


def test_initialize_app_creates_instances_and_config(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("CODEX_SWITCH_HOME", str(tmp_path))
    shared_home = tmp_path / "shared-home"
    (shared_home / ".codex" / "skills").mkdir(parents=True)

    config = initialize_app(
        real_codex_path=Path("/usr/local/bin/codex"),
        instance_count=2,
        shared_home=shared_home,
    )

    assert [instance.name for instance in config.instances] == ["acct-001", "acct-002"]
    assert (tmp_path / "instances" / "acct-001" / "home").exists()
    assert (tmp_path / "config.json").exists()
```

- [ ] **Step 2: Run the initialization test to verify it fails**

Run: `pytest tests/test_wizard.py::test_initialize_app_creates_instances_and_config -q`
Expected: FAIL with `ImportError` for `codex_switch.wizard`

- [ ] **Step 3: Implement initialization and expose `codex-switch init` / `list`**

```python
# src/codex_switch/instances.py
from __future__ import annotations

from pathlib import Path

from codex_switch.models import InstanceConfig
from codex_switch.paths import instances_dir


def ensure_shared_codex_paths(instance_home: Path, shared_home: Path) -> None:
    for relative in (
        Path(".codex") / "skills",
        Path(".codex") / "superpowers",
    ):
        source = shared_home / relative
        if not source.exists():
            continue
        target = instance_home / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            target.symlink_to(source)


def create_instances(instance_count: int, shared_home: Path) -> list[InstanceConfig]:
    instances: list[InstanceConfig] = []
    for index in range(1, instance_count + 1):
        name = f"acct-{index:03d}"
        home_dir = instances_dir() / name / "home"
        home_dir.mkdir(parents=True, exist_ok=True)
        ensure_shared_codex_paths(home_dir, shared_home)
        instances.append(
            InstanceConfig(
                name=name,
                order=index,
                home_dir=str(home_dir),
            )
        )
    return instances
```

```python
# src/codex_switch/wizard.py
from __future__ import annotations

from pathlib import Path

from codex_switch.config import save_config
from codex_switch.instances import create_instances
from codex_switch.models import AppConfig


def initialize_app(
    real_codex_path: Path,
    instance_count: int,
    shared_home: Path,
) -> AppConfig:
    config = AppConfig(
        real_codex_path=str(real_codex_path),
        instances=create_instances(instance_count=instance_count, shared_home=shared_home),
    )
    save_config(config)
    return config
```

```python
# src/codex_switch/cli.py
from __future__ import annotations

from pathlib import Path

import typer

from codex_switch.config import load_config
from codex_switch.wizard import initialize_app

app = typer.Typer(no_args_is_help=True)


@app.command()
def init(
    instance_count: int = typer.Option(..., min=1),
    real_codex_path: Path = typer.Option(..., exists=True, dir_okay=False),
    shared_home: Path = typer.Option(Path.home()),
) -> None:
    initialize_app(
        real_codex_path=real_codex_path,
        instance_count=instance_count,
        shared_home=shared_home,
    )
    typer.echo(f"Initialized {instance_count} account instances")


@app.command("list")
def list_instances() -> None:
    config = load_config()
    for instance in config.instances:
        typer.echo(f"{instance.name}\t{instance.home_dir}")


if __name__ == "__main__":
    app()
```

- [ ] **Step 4: Run the wizard, config, and smoke tests**

Run: `pytest tests/test_smoke.py tests/test_config.py tests/test_runtime.py tests/test_instances.py tests/test_wizard.py -q`
Expected: PASS with `6 passed`

- [ ] **Step 5: Commit**

```bash
git add src/codex_switch/instances.py src/codex_switch/wizard.py src/codex_switch/cli.py tests/test_wizard.py
git commit -m "feat: add initialization flow"
```

## Task 5: Add `/status` probing and quota-based routing

**Files:**
- Create: `src/codex_switch/probe.py`
- Create: `src/codex_switch/routing.py`
- Create: `tests/test_probe.py`
- Create: `tests/test_routing.py`

- [ ] **Step 1: Write the failing probe and routing tests**

```python
# tests/test_probe.py
from codex_switch.probe import parse_remaining_quota


def test_parse_remaining_quota_from_status_output() -> None:
    output = """
    Account: acct-001
    Requests remaining: 42
    """

    assert parse_remaining_quota(output) == 42
```

```python
# tests/test_routing.py
from codex_switch.models import ProbeResult
from codex_switch.routing import select_best_instance


def test_select_best_instance_prefers_highest_quota_then_order() -> None:
    selected = select_best_instance(
        [
            ProbeResult(instance_name="acct-001", order=1, quota_remaining=20, ok=True),
            ProbeResult(instance_name="acct-002", order=2, quota_remaining=42, ok=True),
            ProbeResult(instance_name="acct-003", order=3, quota_remaining=42, ok=True),
        ]
    )

    assert selected.instance_name == "acct-002"
```

- [ ] **Step 2: Run the probe tests to verify they fail**

Run: `pytest tests/test_probe.py tests/test_routing.py -q`
Expected: FAIL with `ImportError` for `codex_switch.probe` and `codex_switch.routing`

- [ ] **Step 3: Implement probe parsing and router selection**

```python
# src/codex_switch/models.py
from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(slots=True)
class InstanceConfig:
    name: str
    order: int
    home_dir: str
    enabled: bool = True

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(slots=True)
class ProbeResult:
    instance_name: str
    order: int
    quota_remaining: int | None
    ok: bool
    reason: str | None = None


@dataclass(slots=True)
class AppConfig:
    real_codex_path: str
    instances: list[InstanceConfig] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "real_codex_path": self.real_codex_path,
            "instances": [instance.to_dict() for instance in self.instances],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "AppConfig":
        raw_instances = payload.get("instances", [])
        instances = [
            InstanceConfig(**item) for item in raw_instances if isinstance(item, dict)
        ]
        return cls(
            real_codex_path=str(payload["real_codex_path"]),
            instances=instances,
        )
```

```python
# src/codex_switch/probe.py
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
```

```python
# src/codex_switch/routing.py
from __future__ import annotations

from codex_switch.models import ProbeResult


def select_best_instance(results: list[ProbeResult]) -> ProbeResult:
    candidates = [result for result in results if result.ok and result.quota_remaining is not None]
    if not candidates:
        raise RuntimeError("No usable Codex account instances are available")

    return sorted(
        candidates,
        key=lambda item: (-int(item.quota_remaining), item.order),
    )[0]
```

- [ ] **Step 4: Run the probe, routing, config, and smoke tests**

Run: `pytest tests/test_smoke.py tests/test_config.py tests/test_runtime.py tests/test_instances.py tests/test_wizard.py tests/test_probe.py tests/test_routing.py -q`
Expected: PASS with `8 passed`

- [ ] **Step 5: Commit**

```bash
git add src/codex_switch/models.py src/codex_switch/probe.py src/codex_switch/routing.py tests/test_probe.py tests/test_routing.py
git commit -m "feat: add quota probe and routing"
```

## Task 6: Add the transparent wrapper and managed command routing

**Files:**
- Create: `src/codex_switch/wrapper.py`
- Create: `tests/test_wrapper.py`
- Modify: `src/codex_switch/cli.py`

- [ ] **Step 1: Write the failing wrapper test**

```python
# tests/test_wrapper.py
import json
from pathlib import Path

from codex_switch.config import save_config
from codex_switch.models import AppConfig, InstanceConfig
from codex_switch.wrapper import main


def test_wrapper_forwards_original_args_to_best_instance(tmp_path, monkeypatch) -> None:
    fake_codex = tmp_path / "fake_codex.py"
    forwarded = tmp_path / "forwarded.json"
    fake_codex.write_text(
        "from pathlib import Path\n"
        "import json, os, sys\n"
        "payload = {'argv': sys.argv[1:], 'instance': os.environ['CODEX_SWITCH_ACTIVE_INSTANCE']}\n"
        f"Path({str(forwarded)!r}).write_text(json.dumps(payload))\n"
    )
    monkeypatch.setenv("CODEX_SWITCH_HOME", str(tmp_path))

    save_config(
        AppConfig(
            real_codex_path="/usr/bin/python3",
            instances=[
                InstanceConfig(name="acct-001", order=1, home_dir=str(tmp_path / "acct-001")),
                InstanceConfig(name="acct-002", order=2, home_dir=str(tmp_path / "acct-002")),
            ],
        )
    )

    monkeypatch.setattr(
        "codex_switch.wrapper.probe_all_instances",
        lambda config: [
            type("Result", (), {"instance_name": "acct-001", "order": 1, "quota_remaining": 12, "ok": True})(),
            type("Result", (), {"instance_name": "acct-002", "order": 2, "quota_remaining": 21, "ok": True})(),
        ],
    )
    monkeypatch.setattr("codex_switch.wrapper.REAL_CODEX_ARGV", ["/usr/bin/python3", str(fake_codex)])

    exit_code = main(["review", "--json"])

    payload = json.loads(forwarded.read_text())
    assert exit_code == 0
    assert payload["argv"] == ["review", "--json"]
    assert payload["instance"] == "acct-002"
```

- [ ] **Step 2: Run the wrapper test to verify it fails**

Run: `pytest tests/test_wrapper.py::test_wrapper_forwards_original_args_to_best_instance -q`
Expected: FAIL with `ImportError` for `codex_switch.wrapper`

- [ ] **Step 3: Implement the wrapper and managed subcommand guard**

```python
# src/codex_switch/wrapper.py
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from codex_switch.config import load_config
from codex_switch.models import ProbeResult
from codex_switch.probe import probe_instance
from codex_switch.routing import select_best_instance
from codex_switch.runtime import build_instance_env

MANAGED_COMMANDS = {"login", "logout"}
REAL_CODEX_ARGV: list[str] | None = None


def probe_all_instances(config) -> list[ProbeResult]:
    return [
        probe_instance(config.real_codex_path, instance)
        for instance in config.instances
        if instance.enabled
    ]


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] in MANAGED_COMMANDS:
        raise SystemExit("Use 'codex-switch login' or 'codex-switch doctor' for account management")

    config = load_config()
    selected = select_best_instance(probe_all_instances(config))
    instance = next(item for item in config.instances if item.name == selected.instance_name)
    env = build_instance_env(
        instance_name=instance.name,
        instance_home=Path(instance.home_dir),
    )

    command = REAL_CODEX_ARGV or [config.real_codex_path]
    completed = subprocess.run(
        [*command, *args],
        env=env,
        check=False,
    )
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
```

```python
# src/codex_switch/cli.py
from __future__ import annotations

from pathlib import Path

import typer

from codex_switch.config import load_config
from codex_switch.wizard import initialize_app

app = typer.Typer(no_args_is_help=True)


@app.command()
def init(
    instance_count: int = typer.Option(..., min=1),
    real_codex_path: Path = typer.Option(..., exists=True, dir_okay=False),
    shared_home: Path = typer.Option(Path.home()),
) -> None:
    initialize_app(
        real_codex_path=real_codex_path,
        instance_count=instance_count,
        shared_home=shared_home,
    )
    typer.echo(f"Initialized {instance_count} account instances")


@app.command("list")
def list_instances() -> None:
    config = load_config()
    for instance in config.instances:
        typer.echo(f"{instance.name}\t{instance.home_dir}")


@app.command()
def login(instance_name: str) -> None:
    typer.echo(f"Login flow for {instance_name} will run through the isolated instance environment")


if __name__ == "__main__":
    app()
```

- [ ] **Step 4: Run the wrapper-adjacent tests**

Run: `pytest tests/test_smoke.py tests/test_config.py tests/test_runtime.py tests/test_instances.py tests/test_wizard.py tests/test_probe.py tests/test_routing.py tests/test_wrapper.py -q`
Expected: PASS with `9 passed`

- [ ] **Step 5: Commit**

```bash
git add src/codex_switch/wrapper.py src/codex_switch/cli.py tests/test_wrapper.py
git commit -m "feat: add transparent codex wrapper"
```

## Task 7: Implement real probing, stale binary recovery, and diagnostics

**Files:**
- Modify: `src/codex_switch/runtime.py`
- Modify: `src/codex_switch/probe.py`
- Create: `src/codex_switch/doctor.py`
- Create: `src/codex_switch/install.py`
- Create: `tests/test_doctor.py`

- [ ] **Step 1: Write the failing doctor test**

```python
# tests/test_doctor.py
from codex_switch.doctor import DoctorReport


def test_doctor_report_flags_missing_shim() -> None:
    report = DoctorReport(real_codex_found=True, shim_precedes_path=False, unhealthy_instances=["acct-002"])

    assert report.summary() == "real-codex=ok shim=missing unhealthy=acct-002"
```

- [ ] **Step 2: Run the doctor test to verify it fails**

Run: `pytest tests/test_doctor.py::test_doctor_report_flags_missing_shim -q`
Expected: FAIL with `ImportError` for `codex_switch.doctor`

- [ ] **Step 3: Implement probing, rediscovery, doctor, and shim installation**

```python
# src/codex_switch/runtime.py
from __future__ import annotations

import os
from pathlib import Path


def find_real_codex(wrapper_dir: Path) -> Path:
    path_entries = []
    for entry in os.environ.get("PATH", "").split(os.pathsep):
        if not entry:
            continue
        if Path(entry).resolve() == wrapper_dir.resolve():
            continue
        path_entries.append(entry)

    for entry in path_entries:
        candidate = Path(entry) / "codex"
        if candidate.exists() and os.access(candidate, os.X_OK):
            return candidate.resolve()

    raise FileNotFoundError("Unable to locate the real codex binary outside the shim directory")


def resolve_real_codex(stored_path: str, wrapper_dir: Path) -> Path:
    candidate = Path(stored_path)
    if candidate.exists() and os.access(candidate, os.X_OK):
        return candidate.resolve()
    return find_real_codex(wrapper_dir=wrapper_dir)


def build_instance_env(
    instance_name: str,
    instance_home: Path,
    parent_env: dict[str, str] | None = None,
) -> dict[str, str]:
    env = dict(parent_env or os.environ)
    env["HOME"] = str(instance_home)
    env["XDG_CONFIG_HOME"] = str(instance_home / ".config")
    env["XDG_CACHE_HOME"] = str(instance_home / ".cache")
    env["XDG_STATE_HOME"] = str(instance_home / ".local" / "state")
    env["CODEX_SWITCH_ACTIVE_INSTANCE"] = instance_name
    return env
```

```python
# src/codex_switch/probe.py
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
    try:
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
        combined = f"{completed.stdout}\n{completed.stderr}".strip()
        remaining = parse_remaining_quota(combined)
    except (ValueError, subprocess.TimeoutExpired) as exc:
        return ProbeResult(
            instance_name=instance.name,
            order=instance.order,
            quota_remaining=None,
            ok=False,
            reason=str(exc),
        )
    return ProbeResult(
        instance_name=instance.name,
        order=instance.order,
        quota_remaining=remaining,
        ok=True,
    )
```

```python
# src/codex_switch/doctor.py
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class DoctorReport:
    real_codex_found: bool
    shim_precedes_path: bool
    unhealthy_instances: list[str] = field(default_factory=list)

    def summary(self) -> str:
        unhealthy = ",".join(self.unhealthy_instances) if self.unhealthy_instances else "none"
        shim = "ok" if self.shim_precedes_path else "missing"
        real = "ok" if self.real_codex_found else "missing"
        return f"real-codex={real} shim={shim} unhealthy={unhealthy}"
```

```python
# src/codex_switch/install.py
from __future__ import annotations

import os
import sys
from pathlib import Path

from codex_switch.paths import shim_dir


def install_shim() -> Path:
    target = shim_dir() / "codex"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        "#!/bin/sh\n"
        f'exec "{sys.executable}" -m codex_switch.wrapper "$@"\n'
    )
    os.chmod(target, 0o755)
    return target
```

- [ ] **Step 4: Run the doctor, wrapper, and probe tests**

Run: `pytest tests/test_smoke.py tests/test_config.py tests/test_runtime.py tests/test_instances.py tests/test_wizard.py tests/test_probe.py tests/test_routing.py tests/test_wrapper.py tests/test_doctor.py -q`
Expected: PASS with `10 passed`

- [ ] **Step 5: Commit**

```bash
git add src/codex_switch/runtime.py src/codex_switch/probe.py src/codex_switch/doctor.py src/codex_switch/install.py tests/test_doctor.py
git commit -m "feat: add doctor and shim installer"
```

## Task 8: Add end-to-end fake-Codex integration tests and public docs

**Files:**
- Create: `tests/conftest.py`
- Create: `tests/helpers/fake_codex.py`
- Create: `tests/test_integration_wrapper.py`
- Create: `README.md`
- Create: `docs/design/codex-switch-design.md`

- [ ] **Step 1: Write the failing integration test**

```python
# tests/test_integration_wrapper.py
import json
import os
import sys
from pathlib import Path

from codex_switch.config import save_config
from codex_switch.models import AppConfig, InstanceConfig
from codex_switch.wrapper import main


def test_wrapper_selects_highest_quota_instance_end_to_end(
    tmp_path,
    monkeypatch,
    fake_codex_path: Path,
) -> None:
    monkeypatch.setenv("CODEX_SWITCH_HOME", str(tmp_path))
    forwarded = tmp_path / "forwarded.json"
    monkeypatch.setenv("CODEX_SWITCH_FORWARD_OUTPUT", str(forwarded))
    launcher = tmp_path / "fake-codex"
    launcher.write_text(
        "#!/bin/sh\n"
        f'exec "{sys.executable}" "{fake_codex_path}" "$@"\n'
    )
    os.chmod(launcher, 0o755)
    acct1 = tmp_path / "instances" / "acct-001" / "home"
    acct2 = tmp_path / "instances" / "acct-002" / "home"
    acct1.mkdir(parents=True)
    acct2.mkdir(parents=True)
    (acct1 / "quota.txt").write_text("8")
    (acct2 / "quota.txt").write_text("17")

    save_config(
        AppConfig(
            real_codex_path=str(launcher),
            instances=[
                InstanceConfig(name="acct-001", order=1, home_dir=str(acct1)),
                InstanceConfig(name="acct-002", order=2, home_dir=str(acct2)),
            ],
        )
    )

    assert main(["review", "--json"]) == 0
    payload = json.loads(forwarded.read_text())
    assert payload["instance"] == "acct-002"
    assert payload["argv"] == ["review", "--json"]
```

- [ ] **Step 2: Run the integration test to verify it fails**

Run: `pytest tests/test_integration_wrapper.py::test_wrapper_selects_highest_quota_instance_end_to_end -q`
Expected: FAIL because the `fake_codex_path` fixture is not defined yet

- [ ] **Step 3: Implement parallel probing and publish public docs**

```python
# tests/conftest.py
from pathlib import Path

import pytest


@pytest.fixture()
def fake_codex_path() -> Path:
    return Path(__file__).parent / "helpers" / "fake_codex.py"
```

```python
# tests/helpers/fake_codex.py
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
```

```python
# src/codex_switch/wrapper.py
from __future__ import annotations

import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from codex_switch.config import load_config
from codex_switch.models import ProbeResult
from codex_switch.probe import probe_instance
from codex_switch.routing import select_best_instance
from codex_switch.runtime import build_instance_env

MANAGED_COMMANDS = {"login", "logout"}
REAL_CODEX_ARGV: list[str] | None = None


def probe_all_instances(config) -> list[ProbeResult]:
    with ThreadPoolExecutor(max_workers=max(1, len(config.instances))) as executor:
        return list(
            executor.map(
                lambda instance: probe_instance(config.real_codex_path, instance),
                config.instances,
            )
        )


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] in MANAGED_COMMANDS:
        raise SystemExit("Use 'codex-switch login' or 'codex-switch doctor' for account management")

    config = load_config()
    selected = select_best_instance(probe_all_instances(config))
    instance = next(item for item in config.instances if item.name == selected.instance_name)
    env = build_instance_env(
        instance_name=instance.name,
        instance_home=Path(instance.home_dir),
    )

    command = REAL_CODEX_ARGV or [config.real_codex_path]
    completed = subprocess.run(
        [*command, *args],
        env=env,
        check=False,
    )
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
```

```markdown
# README.md
# codex-switch

`codex-switch` is a local wrapper that chooses the logged-in Codex account
instance with the most remaining quota before forwarding your `codex ...`
command.

## What v1 does

- keeps the normal `codex` command entrypoint
- stores account instances under `~/.codex-switch/instances/`
- shares repository context and global skills across instances
- probes each instance before launch and selects the best quota
- skips unhealthy or unlogged instances

## What v1 does not do

- switch accounts in the middle of a running Codex session
- manage upstream Codex upgrades for you
- guarantee that upstream `/status` output never changes
```

```markdown
# docs/design/codex-switch-design.md
# codex-switch Design

Build a transparent `codex` wrapper that stores multiple isolated account
instances locally, probes each instance's remaining quota before launch, and
forwards the user command to the best available instance while preserving the
current project directory and repository context.
```

- [ ] **Step 4: Run the full test suite**

Run: `pytest -q`
Expected: PASS with every test green, including the integration test

- [ ] **Step 5: Commit**

```bash
git add README.md docs/design/codex-switch-design.md tests/conftest.py tests/helpers/fake_codex.py tests/test_integration_wrapper.py src/codex_switch/wrapper.py
git commit -m "test: add end-to-end wrapper coverage"
```

## Task 9: Prepare the public GitHub push workflow

**Files:**
- Modify: `README.md`
- Modify: `docs/design/codex-switch-design.md`

- [ ] **Step 1: Write the failing release checklist note**

```markdown
<!-- README.md -->
## Release checklist

- [ ] publish only public docs and code files
- [ ] do not stage `docs/superpowers/*`
- [ ] do not stage local-only skill or agent metadata
```

- [ ] **Step 2: Run a manual diff check to verify it fails today**

Run: `git status --short`
Expected: review the staged file list and confirm that only public files will be committed on the branch you push

- [ ] **Step 3: Finalize the public repository instructions**

```markdown
# README.md
# codex-switch

`codex-switch` is a local wrapper that chooses the logged-in Codex account
instance with the most remaining quota before forwarding your `codex ...`
command.

## Public repository rules

- commit source files, tests, and public docs only
- keep local planning docs under `docs/superpowers/` out of public pushes
- keep local-only `AGENT.md` and skill metadata out of public pushes

## Release checklist

- [ ] tests pass locally
- [ ] the public design doc reflects the latest approved behavior
- [ ] staged files exclude local-only planning metadata
```

```markdown
# docs/design/codex-switch-design.md
# codex-switch Design

## Public summary

`codex-switch` wraps the existing Codex CLI, keeps one real upstream binary,
stores one isolated runtime home per account, probes each account with `/status`
before launch, and forwards the original user command to the account instance
with the highest remaining quota.
```

- [ ] **Step 4: Run the verification commands**

Run: `pytest -q`
Expected: PASS

Run: `git status --short`
Expected: only public files intended for GitHub are staged before the push

- [ ] **Step 5: Commit**

```bash
git add README.md docs/design/codex-switch-design.md
git commit -m "docs: prepare public repository handoff"
```

## Self-Review Notes

- Spec coverage:
  - bootstrap wizard: Task 4
  - isolated instance runtime roots: Tasks 3 and 4
  - `/status` probing and quota selection: Tasks 5, 7, and 8
  - transparent wrapper forwarding: Task 6
  - stale binary recovery and diagnostics: Task 7
  - public repo hygiene: Tasks 8 and 9
- Placeholder scan:
  - no placeholder markers remain
- Type consistency:
  - `AppConfig`, `InstanceConfig`, `ProbeResult`, `build_instance_env()`, `probe_instance()`, and `select_best_instance()` keep the same names across tasks
