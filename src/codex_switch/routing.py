from __future__ import annotations

from codex_switch.models import ProbeResult


def select_best_instance(results: list[ProbeResult]) -> ProbeResult:
    candidates = [
        result for result in results if result.ok and result.quota_remaining is not None
    ]
    if not candidates:
        raise RuntimeError("No usable Codex account instances are available")

    return sorted(
        candidates,
        key=lambda item: (-int(item.quota_remaining), item.order),
    )[0]
