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
        if not isinstance(payload, dict):
            raise ValueError("config payload must be a mapping")

        real_codex_path = payload.get("real_codex_path")
        if not isinstance(real_codex_path, str) or not real_codex_path:
            raise ValueError("real_codex_path must be a non-empty string")

        raw_instances = payload.get("instances", [])
        if not isinstance(raw_instances, list):
            raise ValueError("instances must be a list")

        instances = []
        for item in raw_instances:
            if not isinstance(item, dict):
                raise ValueError("each instance must be a mapping")

            name = item.get("name")
            order = item.get("order")
            home_dir = item.get("home_dir")
            enabled = item.get("enabled", True)

            if not isinstance(name, str) or not name:
                raise ValueError("instance name must be a non-empty string")
            if not isinstance(order, int) or isinstance(order, bool):
                raise ValueError("instance order must be an integer")
            if not isinstance(home_dir, str) or not home_dir:
                raise ValueError("instance home_dir must be a non-empty string")
            if not isinstance(enabled, bool):
                raise ValueError("instance enabled must be a boolean")

            instances.append(
                InstanceConfig(
                    name=name,
                    order=order,
                    home_dir=home_dir,
                    enabled=enabled,
                )
            )

        return cls(
            real_codex_path=real_codex_path,
            instances=instances,
        )
