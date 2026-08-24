from __future__ import annotations

import json
from pathlib import Path

# Deliberately outside this project directory: uvicorn --reload watches the
# whole tree it runs from, and a ledger.json here would trigger a restart on
# every transfer.
LEDGER_PATH = Path("/tmp/durable-banking-ledger.json")

DEFAULT_STATE = {
    "accounts": {
        "A": {
            "balance": 5000.0,
            "home_country": "United States",
            "last_location": {"city": "New York", "country": "United States", "lat": 40.7128, "lon": -74.0060},
            "last_transaction_at": "2026-01-01T00:00:00+00:00",
        },
        "B": {
            "balance": 3000.0,
            "home_country": "United Kingdom",
            "last_location": {"city": "London", "country": "United Kingdom", "lat": 51.5074, "lon": -0.1278},
            "last_transaction_at": "2026-01-01T00:00:00+00:00",
        },
    },
    "applied_workflow_ids": [],
}


def _load() -> dict:
    if not LEDGER_PATH.exists():
        _save(DEFAULT_STATE)
    return json.loads(LEDGER_PATH.read_text())


def _save(state: dict) -> None:
    LEDGER_PATH.write_text(json.dumps(state, indent=2))


def reset() -> None:
    _save(DEFAULT_STATE)


def get_account(account_id: str) -> dict:
    return _load()["accounts"][account_id]


def apply_transfer(
    *, workflow_id: str, from_account: str, to_account: str, amount: float, new_location: dict, new_at: str
) -> dict:
    """Debit/credit the ledger, keyed on workflow_id so a resumed run can't double-apply."""
    state = _load()
    if workflow_id in state["applied_workflow_ids"]:
        return state["accounts"][from_account]

    accounts = state["accounts"]
    if from_account not in accounts or to_account not in accounts:
        raise ValueError(f"unknown account: {from_account if from_account not in accounts else to_account}")
    if amount <= 0:
        raise ValueError("amount must be positive")
    if accounts[from_account]["balance"] < amount:
        raise ValueError(f"insufficient funds in account {from_account}")

    accounts[from_account]["balance"] -= amount
    accounts[to_account]["balance"] += amount
    accounts[from_account]["last_location"] = new_location
    accounts[from_account]["last_transaction_at"] = new_at
    state["applied_workflow_ids"].append(workflow_id)
    _save(state)
    return accounts[from_account]
