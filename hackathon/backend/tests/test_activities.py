import httpx
import pytest
from temporalio.exceptions import ApplicationError

import activities
from fraud_check import FraudDecision


class _FakeResponse:
    def __init__(self, json_data, status_code=200):
        self._json_data = json_data
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=None, response=self)

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


async def test_geolocate_ip_success(monkeypatch):
    fake_data = {"status": "success", "city": "Tokyo", "country": "Japan", "lat": 35.6, "lon": 139.7}
    monkeypatch.setattr(httpx, "AsyncClient", lambda: _FakeAsyncClient(_FakeResponse(fake_data)))

    result = await activities.geolocate_ip("133.242.0.3")
    assert result == {"city": "Tokyo", "country": "Japan", "lat": 35.6, "lon": 139.7}


async def test_geolocate_ip_api_failure_status_raises(monkeypatch):
    # ip-api.com returns HTTP 200 with a body-level "fail" status for e.g. private IP ranges -
    # this must not be silently treated as success.
    fake_data = {"status": "fail", "message": "private range", "query": "10.0.0.1"}
    monkeypatch.setattr(httpx, "AsyncClient", lambda: _FakeAsyncClient(_FakeResponse(fake_data)))

    with pytest.raises(RuntimeError, match="geolocation failed"):
        await activities.geolocate_ip("10.0.0.1")


async def test_get_account_for_transfer_unknown_is_non_retryable_application_error(isolated_ledger):
    with pytest.raises(ApplicationError) as exc_info:
        await activities.get_account_for_transfer("Z")
    assert exc_info.value.non_retryable is True
    assert "Z" in str(exc_info.value)


async def test_get_account_for_transfer_valid(isolated_ledger):
    account = await activities.get_account_for_transfer("A")
    assert account["balance"] == 5000.0


async def test_check_transfer_for_fraud_wraps_the_agent_decision(monkeypatch):
    async def fake_decision(**kwargs):
        return FraudDecision(approve=False, reason="impossible travel detected")

    monkeypatch.setattr(activities, "_check_transfer_for_fraud", fake_decision)

    result = await activities.check_transfer_for_fraud(
        "United States", "New York", "United States", "2026-01-01T00:00:00+00:00",
        "Sydney", "Australia", "2026-01-01T01:00:00+00:00",
        16000.0, 1.0, 16000.0,
    )
    assert result == {"approve": False, "reason": "impossible travel detected"}


async def test_apply_transfer_to_ledger_valid(isolated_ledger):
    result = await activities.apply_transfer_to_ledger(
        "A", "B", 50.0,
        {"city": "London", "country": "United Kingdom", "lat": 51.5, "lon": -0.1},
        "2026-01-02T00:00:00+00:00",
        "wf-1",
    )
    assert result["balance"] == 4950.0


async def test_apply_transfer_to_ledger_missing_workflow_id_raises_typeerror(isolated_ledger):
    # This is exactly what happens if TODO B (transfer_workflow.py's call site) is left unfilled:
    # the call is missing its last positional argument.
    with pytest.raises(TypeError, match="workflow_id"):
        await activities.apply_transfer_to_ledger(
            "A", "B", 50.0,
            {"city": "London", "country": "United Kingdom", "lat": 51.5, "lon": -0.1},
            "2026-01-02T00:00:00+00:00",
        )


@pytest.mark.parametrize(
    "from_account,to_account,amount",
    [
        ("Z", "B", 50.0),      # unknown sender
        ("A", "Z", 50.0),      # unknown receiver
        ("A", "B", 0.0),       # non-positive amount
        ("A", "B", -5.0),      # negative amount
        ("A", "B", 999_999.0), # insufficient funds
    ],
)
async def test_apply_transfer_to_ledger_bad_input_is_non_retryable_application_error(
    isolated_ledger, from_account, to_account, amount
):
    with pytest.raises(ApplicationError) as exc_info:
        await activities.apply_transfer_to_ledger(
            from_account, to_account, amount, {}, "2026-01-01T00:00:00+00:00", "wf-1",
        )
    assert exc_info.value.non_retryable is True
