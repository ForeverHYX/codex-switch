from codex_switch.probe import parse_remaining_quota


def test_parse_remaining_quota_from_status_output() -> None:
    output = """
    Account: acct-001
    Requests remaining: 42
    """

    assert parse_remaining_quota(output) == 42
