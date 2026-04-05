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
