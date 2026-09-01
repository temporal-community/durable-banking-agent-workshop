from __future__ import annotations

import uuid

import httpx
import pytest
from temporalio import activity
from temporalio.client import WorkflowFailureError
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

import activities
import main
from transfer_workflow import TransferWorkflow

# POST /transfer is fire-and-forget (matches solution/backend): it always returns 200 with a
# workflow ID immediately, even for inputs that end up failing. The actual outcome - including
# every validation error below - only shows up later via GET /transfer/{id}, so these tests start
# a transfer through the API, then read the result straight off the workflow handle (which
# resolves instantly under WorkflowEnvironment's time-skipping, no real polling needed).


@activity.defn(name="geolocate_ip")
async def _geolocate_ip_paris(ip: str) -> dict:
    return {"city": "Paris", "country": "France", "lat": 48.8566, "lon": 2.3522}


@activity.defn(name="check_transfer_for_fraud")
async def _approve(*args) -> dict:
    return {"approve": True, "reason": "ok"}


@pytest.fixture
async def api_client(isolated_ledger, monkeypatch):
    task_queue = f"test-api-tq-{uuid.uuid4()}"

    # httpx.AsyncClient over ASGITransport, not FastAPI's sync TestClient: TestClient runs the
    # app in its own thread with its own event loop, which deadlocks against a Temporal client
    # created on this fixture's (different) event loop. Staying on one event loop end to end
    # avoids that - test_fragility.py's concurrent-transfer test already used this same pattern
    # against the old synchronous app.
    async with await WorkflowEnvironment.start_time_skipping() as env:
        worker = Worker(
            env.client,
            task_queue=task_queue,
            workflows=[TransferWorkflow],
            activities=[
                _geolocate_ip_paris,
                activities.get_account_for_transfer,
                _approve,
                activities.apply_transfer_to_ledger,
            ],
        )
        async with worker:
            monkeypatch.setattr(main, "client", env.client)
            monkeypatch.setattr(main, "TASK_QUEUE", task_queue)
            transport = httpx.ASGITransport(app=main.app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as http_client:
                yield main.client, http_client


async def _start(http_client, **overrides) -> str:
    body = {"from_account": "A", "to_account": "B", "amount": 10, "spoof_location": None, **overrides}
    res = await http_client.post("/transfer", json=body)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "pending"
    return data["workflow_id"]


async def _await_failure_detail(client, workflow_id: str) -> str:
    handle = client.get_workflow_handle(workflow_id)
    with pytest.raises(WorkflowFailureError) as exc_info:
        await handle.result()
    cause = exc_info.value
    while getattr(cause, "cause", None) is not None:
        cause = cause.cause
    return str(cause)


async def test_get_account_returns_seeded_balance(api_client):
    _client, http_client = api_client
    res = await http_client.get("/accounts/A")
    assert res.status_code == 200
    body = res.json()
    assert body["balance"] == 5000.0
    assert body["home_country"] == "United States"

    res = await http_client.get("/accounts/B")
    assert res.status_code == 200
    assert res.json()["balance"] == 3000.0


async def test_get_unknown_account_is_404(api_client):
    _client, http_client = api_client
    res = await http_client.get("/accounts/nonexistent")
    assert res.status_code == 404


async def test_transfer_unknown_from_account_fails_the_workflow(api_client):
    client, http_client = api_client
    workflow_id = await _start(http_client, from_account="Z")
    detail = await _await_failure_detail(client, workflow_id)
    assert "no such account" in detail


async def test_transfer_zero_amount_fails_the_workflow(api_client):
    client, http_client = api_client
    workflow_id = await _start(http_client, amount=0)
    detail = await _await_failure_detail(client, workflow_id)
    assert "positive" in detail


async def test_transfer_negative_amount_fails_the_workflow(api_client):
    client, http_client = api_client
    workflow_id = await _start(http_client, amount=-50)
    detail = await _await_failure_detail(client, workflow_id)
    assert "positive" in detail


async def test_transfer_exceeding_balance_fails_the_workflow(api_client):
    client, http_client = api_client
    workflow_id = await _start(http_client, amount=999_999)
    detail = await _await_failure_detail(client, workflow_id)
    assert "insufficient" in detail.lower()


async def test_transfer_unknown_spoof_location_fails_the_workflow(api_client):
    client, http_client = api_client
    workflow_id = await _start(http_client, spoof_location="Atlantis")
    detail = await _await_failure_detail(client, workflow_id)
    assert "unknown spoof location" in detail.lower()


async def test_transfer_status_endpoint_surfaces_the_same_failure(api_client):
    _client, http_client = api_client
    workflow_id = await _start(http_client, amount=0)

    for _ in range(20):
        res = await http_client.get(f"/transfer/{workflow_id}")
        assert res.status_code == 200
        data = res.json()
        if data["status"] == "FAILED":
            assert "positive" in data["error"]
            return
    pytest.fail("workflow never reached FAILED status")
