from pathlib import Path

import pytest


@pytest.fixture()
def fake_codex_path() -> Path:
    return Path(__file__).parent / "helpers" / "fake_codex.py"
