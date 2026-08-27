"""Tests that document known, INTENTIONAL fragility of hackathon/backend.

hackathon/backend is deliberately non-durable: no retries, in-memory state, no idempotency,
no locking. These tests exist to demonstrate that fragility as a real, reproducible property of
the design - not to flag bugs to fix here. `solution/backend`'s Temporal workflow is the fix.
"""

from __future__ import annotations

import asyncio

import httpx

import main
from fraud_check import FraudDecision


def test_geo_ip_failure_propagates_as_500_no_retry(client, mock_geo_failure, mock_fraud_approve):
    """Intentional: main.py awaits geolocate_ip with no try/except and no retry policy. A flaky
    or refusing geo-IP call just fails the whole request - this is the "no retry" half of the
    workshop's pitch, working exactly as designed.
    """
    res = client.post(
        "/transfer",
        json={"from_account": "A", "to_account": "B", "amount": 10, "spoof_location": "New York"},
    )
    assert res.status_code == 500

    # And because the failure happens before any balance mutation, at least the ledger itself
    # isn't corrupted by this particular failure mode - only concurrent writes are (see below).
    assert client.get("/accounts/A").json()["balance"] == 5000.0


async def test_concurrent_transfers_can_overdraw_the_ledger(monkeypatch):
    """Demonstrates a known, intentional fragility: concurrent transfers can corrupt the
    in-memory ledger because there is no locking around the read-check-write of
    `sender["balance"]`. main.py checks `sender["balance"] < amount` long before it ever awaits
    anything else, then writes the new balance only at the very end, after an `await
    geolocate_ip(...)` and `await check_transfer_for_fraud(...)`. Two concurrent transfers that
    are each individually affordable, but not affordable together, can both pass the balance
    check before either has written back - a classic lost-update race. This is exactly the class
    of bug the workshop's Temporal solution (a single idempotent, effectively-serialized
    ledger-update activity) fixes; it is not a bug to patch in hackathon/backend.
    """

    async def slow_geo(ip: str) -> dict:
        # Forces both concurrent requests past their balance check and into the "in flight"
        # window before either one resumes and writes its result back.
        await asyncio.sleep(0.05)
        return {"city": "Paris", "country": "France", "lat": 48.8566, "lon": 2.3522}

    async def approve(**kwargs) -> FraudDecision:
        return FraudDecision(approve=True, reason="ok")

    monkeypatch.setattr(main, "geolocate_ip", slow_geo)
    monkeypatch.setattr(main, "check_transfer_for_fraud", approve)

    body = {"from_account": "A", "to_account": "B", "amount": 3000, "spoof_location": "New York"}
    # Account A starts at $5000. Two $3000 transfers together exceed that, but each one alone is
    # well within balance at the moment it's checked.
    transport = httpx.ASGITransport(app=main.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http_client:
        responses = await asyncio.gather(
            http_client.post("/transfer", json=body),
            http_client.post("/transfer", json=body),
        )

    assert [r.status_code for r in responses] == [200, 200], (
        "both requests should have individually passed the balance check - that's the race"
    )

    final_balance = main.accounts["A"]["balance"]
    assert final_balance < 0, (
        f"expected the unlocked read-check-write race to overdraw account A, "
        f"got balance={final_balance} instead"
    )
