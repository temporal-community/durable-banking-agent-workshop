from __future__ import annotations

from datetime import datetime, timedelta, timezone
from math import asin, cos, radians, sin, sqrt

from temporalio import workflow
from temporalio.exceptions import ApplicationError
from temporalio.contrib.openai_agents.workflow import activity_as_tool

with workflow.unsafe.imports_passed_through():
    # Pre-imported so the workflow sandbox snapshots pydantic before the first Agent(...).
    import annotated_types  # noqa: F401
    import pydantic_core  # noqa: F401
    import pydantic_core.core_schema  # noqa: F401

    from agents import Agent, Runner, function_tool
    from pydantic import BaseModel

    from activities import (
        SPOOFABLE_LOCATIONS,
        apply_transfer_to_ledger,
        geolocate_ip,
        get_account_for_transfer,
    )

TOOL_TIMEOUT = timedelta(seconds=30)
IMPOSSIBLE_TRAVEL_SPEED_KMH = 900.0
EARTH_RADIUS_KM = 6371.0

INSTRUCTIONS = f"""
You are a fraud investigator for a bank. For the transfer you're given an account ID and an IP
address. Use your tools to look up the account's home country and last-transaction location, to
geolocate the new IP, and to compute the travel distance/time/speed between them. Then decide
whether to approve or decline this transfer.

Impossible travel means the implied speed between the last known location and the new one exceeds
{IMPOSSIBLE_TRAVEL_SPEED_KMH:.0f} km/h, the cruising speed of a commercial flight - no traveler
could plausibly cover that distance in that time. Decline only when the travel is genuinely
implausible; a short trip abroad is not fraud on its own.

Always report the new location's city, country, latitude and longitude in your final answer,
exactly as returned by the geolocation tool.
"""


def travel_metrics_str(
    last_lat: float, last_lon: float, last_at_iso: str, new_lat: float, new_lon: float, now: datetime
) -> str:
    """Pure distance/elapsed-time/speed math, extracted from the workflow's function-tool closure
    so it's testable without a workflow sandbox. `now` is passed in rather than read internally
    since the caller inside the workflow must use workflow.now(), not datetime.now()."""
    lat1, lon1, lat2, lon2 = map(radians, (last_lat, last_lon, new_lat, new_lon))
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    distance_km = 2 * EARTH_RADIUS_KM * asin(sqrt(a))
    last_at = datetime.fromisoformat(last_at_iso)
    if last_at.tzinfo is None:
        # The model round-trips this timestamp through its own tool-call arguments and sometimes
        # drops the UTC offset when reformatting it; every timestamp this workflow ever produces
        # is UTC, so a naive one can only mean that.
        last_at = last_at.replace(tzinfo=timezone.utc)
    elapsed_hours = max((now - last_at).total_seconds() / 3600, 1e-6)
    return (
        f"{distance_km:.0f} km in {elapsed_hours:.2f} hours, "
        f"implying {distance_km / elapsed_hours:.0f} km/h"
    )


class FraudDecision(BaseModel):
    approve: bool
    reason: str
    new_city: str
    new_country: str
    new_lat: float
    new_lon: float


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

        @function_tool
        def compute_travel_metrics(
            last_lat: float, last_lon: float, last_at_iso: str, new_lat: float, new_lon: float
        ) -> str:
            """Compute distance, elapsed time and implied speed between two transactions.

            Args:
                last_lat: Latitude of the account's last transaction.
                last_lon: Longitude of the account's last transaction.
                last_at_iso: ISO timestamp of the account's last transaction.
                new_lat: Latitude of this transaction.
                new_lon: Longitude of this transaction.
            """
            return travel_metrics_str(last_lat, last_lon, last_at_iso, new_lat, new_lon, workflow.now())

        agent = Agent(
            name="FraudInvestigator",
            instructions=INSTRUCTIONS,
            model="gpt-4o",
            tools=[
                activity_as_tool(get_account_for_transfer, start_to_close_timeout=TOOL_TIMEOUT),
                activity_as_tool(geolocate_ip, start_to_close_timeout=TOOL_TIMEOUT),
                compute_travel_metrics,
            ],
            output_type=FraudDecision,
        )

        workflow.logger.info("running fraud check for account=%s ip=%s, pausing for the demo window", from_account, ip)
        await workflow.sleep(timedelta(seconds=10))

        result = await Runner.run(
            agent,
            input=f"Account {from_account} is transferring ${amount} to account {to_account} from IP {ip}. Decide.",
        )
        decision = result.final_output_as(FraudDecision)

        if not decision.approve:
            raise ApplicationError(f"transfer declined: {decision.reason}", non_retryable=True)

        new_location = {
            "city": decision.new_city,
            "country": decision.new_country,
            "lat": decision.new_lat,
            "lon": decision.new_lon,
        }
        account = await workflow.execute_activity(
            apply_transfer_to_ledger,
            args=[workflow.info().workflow_id, from_account, to_account, amount, new_location, workflow.now().isoformat()],
            start_to_close_timeout=timedelta(seconds=10),
        )
        return {"status": "accepted", "from_account": account, "reason": decision.reason}
