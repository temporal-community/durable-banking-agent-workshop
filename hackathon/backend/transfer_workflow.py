from __future__ import annotations

from datetime import datetime, timedelta, timezone
from math import asin, cos, radians, sin, sqrt

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ApplicationError

with workflow.unsafe.imports_passed_through():
    from activities import (
        SPOOFABLE_LOCATIONS,
        apply_transfer_to_ledger,
        check_transfer_for_fraud,
        geolocate_ip,
        get_account_for_transfer,
    )

TOOL_TIMEOUT = timedelta(seconds=30)
EARTH_RADIUS_KM = 6371.0


def travel_metrics(
    last_lat: float, last_lon: float, last_at_iso: str, new_lat: float, new_lon: float, now: datetime
) -> tuple[float, float, float]:
    """Pure distance/elapsed-time/speed math. Extracted from the workflow so it's testable
    without a workflow sandbox. `now` is passed in rather than read internally since the caller
    inside the workflow must use workflow.now(), not datetime.now()."""
    lat1, lon1, lat2, lon2 = map(radians, (last_lat, last_lon, new_lat, new_lon))
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    distance_km = 2 * EARTH_RADIUS_KM * asin(sqrt(a))
    last_at = datetime.fromisoformat(last_at_iso)
    if last_at.tzinfo is None:
        last_at = last_at.replace(tzinfo=timezone.utc)
    elapsed_hours = max((now - last_at).total_seconds() / 3600, 1e-6)
    implied_speed_kmh = distance_km / elapsed_hours
    return distance_km, elapsed_hours, implied_speed_kmh


@workflow.defn
class TransferWorkflow:
    @workflow.run
    async def run(self, from_account: str, to_account: str, amount: float, spoof_location: str | None) -> dict:
        if amount <= 0:
            raise ApplicationError("amount must be positive", non_retryable=True)
        if spoof_location and spoof_location not in SPOOFABLE_LOCATIONS:
            raise ApplicationError(f"unknown spoof location: {spoof_location}", non_retryable=True)
        ip = SPOOFABLE_LOCATIONS.get(spoof_location, "8.8.8.8") if spoof_location else "8.8.8.8"

        sender = await workflow.execute_activity(
            get_account_for_transfer,
            from_account,
            start_to_close_timeout=TOOL_TIMEOUT,
        )
        await workflow.execute_activity(
            get_account_for_transfer,
            to_account,
            start_to_close_timeout=TOOL_TIMEOUT,
        )
        if sender["balance"] < amount:
            raise ApplicationError("insufficient funds", non_retryable=True)

        location = await workflow.execute_activity(
            geolocate_ip,
            ip,
            start_to_close_timeout=TOOL_TIMEOUT,
        )

        now = workflow.now()
        last_location = sender["last_location"]
        distance_km, elapsed_hours, implied_speed_kmh = travel_metrics(
            last_location["lat"],
            last_location["lon"],
            sender["last_transaction_at"],
            location["lat"],
            location["lon"],
            now,
        )

        # TODO: add workflow.sleep(...) here, before the fraud-check call, so there's a
        # guaranteed window to kill the worker mid-transfer for the crash-recovery demo.

        decision = await workflow.execute_activity(
            check_transfer_for_fraud,
            args=[
                sender["home_country"],
                last_location["city"],
                last_location["country"],
                sender["last_transaction_at"],
                location["city"],
                location["country"],
                now.isoformat(),
                distance_km,
                elapsed_hours,
                implied_speed_kmh,
            ],
            start_to_close_timeout=timedelta(seconds=60),
        )

        if not decision["approve"]:
            # TODO: raise ApplicationError(..., non_retryable=True) instead - a genuine decline is
            # permanent, don't let it retry.
            raise ApplicationError("TODO not implemented", non_retryable=False)

        # TODO: pass workflow.info().workflow_id as the idempotency key
        account = await workflow.execute_activity(
            apply_transfer_to_ledger,
            args=[from_account, to_account, amount, location, now.isoformat()],
            start_to_close_timeout=timedelta(seconds=10),
            schedule_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(initial_interval=timedelta(seconds=1)),
        )
        return {"status": "accepted", "from_account": account, "reason": decision["reason"]}
