from __future__ import annotations

from datetime import datetime

import httpx
from temporalio import activity
from temporalio.exceptions import ApplicationError

import ledger
from fraud_check import check_transfer_for_fraud as _check_transfer_for_fraud

# Representative public IPs for each city offered by the frontend's spoof-location dropdown.
SPOOFABLE_LOCATIONS: dict[str, str] = {
    "New York": "8.8.8.8",
    "London": "185.86.151.11",
    "Tokyo": "133.242.0.3",
    "Lagos": "105.112.0.1",
    "Sydney": "1.1.1.1",
}


@activity.defn
async def geolocate_ip(ip: str) -> dict:
    """Look up city, country, latitude and longitude for a public IP via ip-api.com."""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"http://ip-api.com/json/{ip}", timeout=5.0)
        response.raise_for_status()
        data = response.json()
        if data.get("status") != "success":
            raise RuntimeError(f"geolocation failed for {ip}: {data}")
        return {"city": data["city"], "country": data["country"], "lat": data["lat"], "lon": data["lon"]}


@activity.defn
async def get_account_for_transfer(account_id: str) -> dict:
    """Read an account's balance, home country and last-transaction location."""
    try:
        return ledger.get_account(account_id)
    except KeyError:
        raise ApplicationError(f"no such account: {account_id}", non_retryable=True) from None


@activity.defn
async def check_transfer_for_fraud(
    home_country: str,
    last_city: str,
    last_country: str,
    last_at: str,
    new_city: str,
    new_country: str,
    new_at: str,
    distance_km: float,
    elapsed_hours: float,
    implied_speed_kmh: float,
) -> dict:
    """Ask the fraud-check agent to approve or decline a transfer given its travel facts."""
    decision = await _check_transfer_for_fraud(
        home_country=home_country,
        last_city=last_city,
        last_country=last_country,
        last_at=datetime.fromisoformat(last_at),
        new_city=new_city,
        new_country=new_country,
        new_at=datetime.fromisoformat(new_at),
        distance_km=distance_km,
        elapsed_hours=elapsed_hours,
        implied_speed_kmh=implied_speed_kmh,
    )
    return decision.model_dump()


@activity.defn
async def apply_transfer_to_ledger(
    from_account: str, to_account: str, amount: float, new_location: dict, new_at: str, workflow_id: str
) -> dict:
    """Debit and credit the ledger, idempotent on workflow_id so a resumed run can't double-apply.

    workflow_id is last on purpose: leaving it off the call site is this module's TODO B, and it
    should fail loudly as a missing-argument TypeError, not silently double-apply.
    """
    try:
        return ledger.apply_transfer(
            workflow_id=workflow_id,
            from_account=from_account,
            to_account=to_account,
            amount=amount,
            new_location=new_location,
            new_at=new_at,
        )
    except ValueError as exc:
        raise ApplicationError(str(exc), non_retryable=True) from None
