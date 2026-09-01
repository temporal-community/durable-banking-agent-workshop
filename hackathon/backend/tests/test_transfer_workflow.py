import uuid
from datetime import datetime, timezone

import pytest
from temporalio import activity
from temporalio.client import WorkflowFailureError
from temporalio.exceptions import ApplicationError
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

import activities
from transfer_workflow import TransferWorkflow, travel_metrics

NOW = datetime(2026, 1, 2, 12, 0, 0, tzinfo=timezone.utc)

# New York -> London, roughly 5570km apart.
NY = (40.7128, -74.0060)
LONDON = (51.5074, -0.1278)


def test_travel_metrics_aware_timestamp_does_not_raise():
    distance_km, elapsed_hours, implied_speed_kmh = travel_metrics(*NY, "2026-01-01T12:00:00+00:00", *LONDON, NOW)
    assert distance_km > 0 and elapsed_hours > 0 and implied_speed_kmh > 0


def test_travel_metrics_naive_timestamp_does_not_raise():
    # Regression: a naive timestamp (no UTC offset) used to raise "can't subtract offset-naive
    # and offset-aware datetimes".
    distance_km, elapsed_hours, implied_speed_kmh = travel_metrics(*NY, "2026-01-01T12:00:00", *LONDON, NOW)
    assert distance_km > 0 and elapsed_hours > 0 and implied_speed_kmh > 0


def test_travel_metrics_distance_is_realistic_for_ny_to_london():
    distance_km, _, _ = travel_metrics(*NY, "2026-01-01T00:00:00+00:00", *LONDON, NOW)
    assert 5400 <= distance_km <= 5700


def test_travel_metrics_zero_elapsed_time_does_not_divide_by_zero():
    # last transaction "now" and this transaction also "now" - elapsed_hours is clamped to a tiny
    # positive floor (1e-6h) rather than zero, so the speed division can't blow up.
    _, elapsed_hours, implied_speed_kmh = travel_metrics(*NY, NOW.isoformat(), *LONDON, NOW)
    assert elapsed_hours > 0 and implied_speed_kmh > 0


def test_travel_metrics_same_point_is_zero_distance():
    distance_km, _, _ = travel_metrics(*NY, "2026-01-01T00:00:00+00:00", *NY, NOW)
    assert distance_km == 0


TASK_QUEUE = "test-tq"


@activity.defn(name="geolocate_ip")
async def fake_geolocate_ip(ip: str) -> dict:
    return {"city": "London", "country": "United Kingdom", "lat": 51.5074, "lon": -0.1278}


def _fake_check_transfer_for_fraud(approve: bool, reason: str):
    @activity.defn(name="check_transfer_for_fraud")
    async def _fake(*args) -> dict:
        return {"approve": approve, "reason": reason}

    return _fake


async def _run_transfer_workflow(*, approve: bool, reason: str, task_queue: str):
    """Runs TransferWorkflow to completion (or failure) and returns (workflow_id, result,
    failure). The result/exception is captured *inside* the live env/worker context - returning
    an unresolved handle instead would tear the test server down before the caller could ever
    await it, surfacing a confusing RPC connection error instead of the real outcome."""
    async with await WorkflowEnvironment.start_time_skipping() as env:
        worker = Worker(
            env.client,
            task_queue=task_queue,
            workflows=[TransferWorkflow],
            activities=[
                fake_geolocate_ip,
                activities.get_account_for_transfer,
                _fake_check_transfer_for_fraud(approve, reason),
                activities.apply_transfer_to_ledger,
            ],
        )
        async with worker:
            workflow_id = f"transfer-{uuid.uuid4()}"
            handle = await env.client.start_workflow(
                TransferWorkflow.run,
                args=["A", "B", 100.0, None],
                id=workflow_id,
                task_queue=task_queue,
            )
            try:
                result = await handle.result()
                return workflow_id, result, None
            except WorkflowFailureError as exc:
                return workflow_id, None, exc


async def test_ledger_update_is_idempotent_on_workflow_id(isolated_ledger):
    """Runs the real workflow (with TODO B as shipped in transfer_workflow.py) end to end, then
    re-delivers the same ledger-update activity call directly with the same workflow ID -
    simulating a resumed/replayed activity. Only fails clearly if TODO B is unfilled: the
    workflow's call to apply_transfer_to_ledger is then missing its workflow_id argument, so the
    activity raises TypeError and the workflow fails before ever reaching this assertion."""
    workflow_id, _result, exc = await _run_transfer_workflow(
        approve=True, reason="ok", task_queue=TASK_QUEUE + "-idempotency"
    )
    assert exc is None, f"transfer workflow failed: {exc}"

    balance_after_first_transfer = isolated_ledger.get_account("A")["balance"]
    assert balance_after_first_transfer == 4900.0

    # Re-deliver the ledger update with the same workflow_id - must not move money again.
    await activities.apply_transfer_to_ledger(
        "A", "B", 100.0,
        {"city": "London", "country": "United Kingdom", "lat": 51.5074, "lon": -0.1278},
        "2026-01-01T00:00:00+00:00",
        workflow_id,
    )
    assert isolated_ledger.get_account("A")["balance"] == balance_after_first_transfer


async def test_fraud_decline_is_non_retryable_once_todo_c_is_filled_in(isolated_ledger):
    """As shipped (TODO C unfilled), a fraud decline raises ApplicationError(non_retryable=False),
    which fails this assertion clearly. Filling in TODO C (non_retryable=True) makes it pass."""
    _workflow_id, _result, exc = await _run_transfer_workflow(
        approve=False, reason="impossible travel detected", task_queue=TASK_QUEUE + "-decline"
    )
    assert exc is not None, "expected the decline to fail the workflow"

    cause = exc.cause
    assert isinstance(cause, ApplicationError)
    assert cause.non_retryable is True
