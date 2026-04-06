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
