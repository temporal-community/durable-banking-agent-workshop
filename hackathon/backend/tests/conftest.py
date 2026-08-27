from __future__ import annotations

import copy

import pytest
from fastapi.testclient import TestClient

import ledger
import main
from fraud_check import FraudDecision


@pytest.fixture(autouse=True)
def reset_ledger():
    """`ledger.accounts`/`ledger.incidents` are module-level mutable globals, and `main.py`
    imports the same dict/list objects by reference (not a copy). Mutate in place - clear +
    update/extend - so the aliasing survives the reset; reassigning `ledger.accounts = {...}`
    would leave `main.accounts` pointing at the old, now-detached object.
    """
    original_accounts = copy.deepcopy(ledger.accounts)
    original_incidents = list(ledger.incidents)
    yield
    ledger.accounts.clear()
    ledger.accounts.update(copy.deepcopy(original_accounts))
    ledger.incidents.clear()
    ledger.incidents.extend(original_incidents)


@pytest.fixture
def client():
    # raise_server_exceptions=False so an unhandled exception in the route (e.g. a geo-IP
    # failure with no try/except, by design) comes back as a real HTTP 500 response instead of
    # being re-raised into the test - matching what a real uvicorn server would send a caller.
    return TestClient(main.app, raise_server_exceptions=False)


@pytest.fixture
def mock_geo_success(monkeypatch):
    """geolocate_ip always resolves to a fixed, valid location."""

    async def _fake(ip: str) -> dict:
        return {"city": "Paris", "country": "France", "lat": 48.8566, "lon": 2.3522}

    monkeypatch.setattr(main, "geolocate_ip", _fake)
    return _fake


@pytest.fixture
def mock_geo_failure(monkeypatch):
    """geolocate_ip raises, matching geo.py's real behavior when ip-api.com fails or refuses
    the request (e.g. a private IP range)."""

    async def _fake(ip: str) -> dict:
        raise RuntimeError(f"geolocation failed for {ip}: simulated failure")

    monkeypatch.setattr(main, "geolocate_ip", _fake)
    return _fake


@pytest.fixture
def mock_fraud_approve(monkeypatch):
    async def _fake(**kwargs) -> FraudDecision:
        return FraudDecision(approve=True, reason="travel is plausible")

    monkeypatch.setattr(main, "check_transfer_for_fraud", _fake)
    return _fake


@pytest.fixture
def mock_fraud_decline(monkeypatch):
    async def _fake(**kwargs) -> FraudDecision:
        return FraudDecision(approve=False, reason="impossible travel detected")

    monkeypatch.setattr(main, "check_transfer_for_fraud", _fake)
    return _fake
