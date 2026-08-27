import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

import ledger_store


@pytest.fixture
def isolated_ledger(tmp_path, monkeypatch):
    """Points ledger_store at a throwaway file/lock per test so tests never share state with
    each other or with a real running instance's /tmp/durable-banking-ledger.json."""
    monkeypatch.setattr(ledger_store, "LEDGER_PATH", tmp_path / "ledger.json")
    monkeypatch.setattr(ledger_store, "LOCK_PATH", tmp_path / "ledger.lock")
    ledger_store.reset()
    return ledger_store
