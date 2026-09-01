"""Tests that document the fix to hackathon/backend's former fragility, now that it's
Temporalized. The old version of this file exercised the plain synchronous FastAPI app - no
retries, no idempotency, no locking - by hitting real races. That app no longer exists: the same
behavior is now handled by Temporal's own retry policy and the ledger's workflow_id idempotency
key. See tests/test_ledger.py (locking/idempotency at the store level), tests/test_activities.py
(idempotency at the activity boundary) and tests/test_transfer_workflow.py (idempotency and
non-retryable-decline behavior through the actual workflow) for the replacements.

These tests deliberately don't run a transfer through to acceptance: that depends on
transfer_workflow.py's TODOs being filled in, which is exactly what test_transfer_workflow.py's
two dedicated tests check instead.
"""

from __future__ import annotations

import threading

import httpx
import pytest
from temporalio.exceptions import ApplicationError

import activities


class _FakeResponse:
    def __init__(self, json_data):
        self._json_data = json_data

    def raise_for_status(self):
        pass

    def json(self):
        return self._json_data


class _FakeAsyncClient:
    def __init__(self, response):
        self._response = response

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get(self, url, timeout=None):
        return self._response


async def test_geo_ip_failure_is_a_plain_exception_not_a_non_retryable_one(monkeypatch):
    """The old backend had no retry: a flaky or refusing geo-IP call just failed the whole
    request. geolocate_ip's failures are plain exceptions (RuntimeError, httpx errors), never
    ApplicationError(non_retryable=True) - so, unlike an unknown-account lookup, Temporal's
    default activity retry policy applies to them automatically, with no special-casing needed in
    transfer_workflow.py.
    """
    fake_data = {"status": "fail", "message": "private range", "query": "10.0.0.1"}
    monkeypatch.setattr(httpx, "AsyncClient", lambda: _FakeAsyncClient(_FakeResponse(fake_data)))

    with pytest.raises(RuntimeError, match="geolocation failed"):
        await activities.geolocate_ip("10.0.0.1")


async def test_unknown_account_lookup_is_non_retryable_unlike_a_geo_failure(isolated_ledger):
    """Contrast case: an unknown account is a permanent, not transient, problem - so
    get_account_for_transfer wraps it as ApplicationError(non_retryable=True), which Temporal
    will not retry, unlike the plain exception above."""
    with pytest.raises(ApplicationError) as exc_info:
        await activities.get_account_for_transfer("nonexistent")
    assert exc_info.value.non_retryable is True


def test_concurrent_transfers_no_longer_overdraw_the_ledger(isolated_ledger):
    """Regression test for the fixed version of a real race the old in-memory ledger had: two
    concurrent transfers that are each individually affordable, but not affordable together,
    used to both pass a balance check before either wrote back - a lost-update race. The
    file-backed, flock-protected ledger re-validates the balance under its own lock, so only one
    of two such transfers can succeed now."""
    results = []

    def send(i: int) -> None:
        try:
            isolated_ledger.apply_transfer(
                workflow_id=f"wf-{i}",
                from_account="A",
                to_account="B",
                amount=3000.0,
                new_location={"city": "Paris", "country": "France", "lat": 48.8566, "lon": 2.3522},
                new_at="2026-01-02T00:00:00+00:00",
            )
            results.append("ok")
        except ValueError:
            results.append("rejected")

    threads = [threading.Thread(target=send, args=(i,)) for i in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Account A starts at $5000. Two $3000 transfers together exceed that; exactly one must win.
    assert sorted(results) == ["ok", "rejected"]
    assert isolated_ledger.get_account("A")["balance"] == 2000.0
