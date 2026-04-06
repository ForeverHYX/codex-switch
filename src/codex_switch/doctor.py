from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from codex_switch.config import ConfigCorruptError, ConfigNotInitializedError, load_config
from codex_switch.install import active_shim_path, runtime_wrapper_dir
from codex_switch.probe import probe_instance
from codex_switch.runtime import resolve_real_codex


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


def shim_precedes_path(wrapper_dir: Path | None = None) -> bool:
    active = active_shim_path(os.environ.get("PATH", ""))
    if active is None:
        return False
    if wrapper_dir is None:
        return True
    return active.parent.resolve() == wrapper_dir.resolve()


def create_doctor_report(wrapper_dir: Path | None = None) -> DoctorReport:
    actual_wrapper_dir = wrapper_dir or runtime_wrapper_dir()
    shim_ok = shim_precedes_path(actual_wrapper_dir)

    try:
        config = load_config()
    except (ConfigNotInitializedError, ConfigCorruptError):
        return DoctorReport(real_codex_found=False, shim_precedes_path=shim_ok)

    try:
        real_codex_path = resolve_real_codex(config.real_codex_path, actual_wrapper_dir)
    except FileNotFoundError:
        unhealthy_instances = [instance.name for instance in config.instances if instance.enabled]
        return DoctorReport(
            real_codex_found=False,
            shim_precedes_path=shim_ok,
            unhealthy_instances=unhealthy_instances,
        )

    unhealthy_instances = [
        result.instance_name
        for result in (
            probe_instance(str(real_codex_path), instance)
            for instance in config.instances
            if instance.enabled
        )
        if not result.ok
    ]
    return DoctorReport(
        real_codex_found=True,
        shim_precedes_path=shim_ok,
        unhealthy_instances=unhealthy_instances,
    )
