import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

import ledger


@pytest.fixture
def isolated_ledger(tmp_path, monkeypatch):
    """Points ledger at a throwaway file/lock per test so tests never share state with each
    other or with a real running instance's /tmp/durable-banking-ledger-hackathon.json."""
    monkeypatch.setattr(ledger, "LEDGER_PATH", tmp_path / "ledger.json")
    monkeypatch.setattr(ledger, "LOCK_PATH", tmp_path / "ledger.lock")
    ledger.reset()
    return ledger
