from __future__ import annotations

import httpx
from temporalio import activity
from temporalio.exceptions import ApplicationError

import ledger_store

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
    """Look up city, country, latitude and longitude for a public IP via ip-api.com.

    Args:
        ip: A public IPv4 or IPv6 address.
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(f"http://ip-api.com/json/{ip}", timeout=5.0)
        response.raise_for_status()
        data = response.json()
        if data.get("status") != "success":
            raise RuntimeError(f"geolocation failed for {ip}: {data}")
        return {"city": data["city"], "country": data["country"], "lat": data["lat"], "lon": data["lon"]}


@activity.defn
async def get_account_for_transfer(account_id: str) -> dict:
    """Read an account's balance, home country and last-transaction location.

    Args:
        account_id: The account identifier, e.g. "A" or "B".
    """
    try:
        return ledger_store.get_account(account_id)
    except KeyError:
        raise ApplicationError(f"no such account: {account_id}", non_retryable=True) from None


@activity.defn
async def apply_transfer_to_ledger(
    workflow_id: str, from_account: str, to_account: str, amount: float, new_location: dict, new_at: str
) -> dict:
    """Debit and credit the ledger, idempotent on workflow_id so a resumed run can't double-apply.

    Args:
        workflow_id: The transfer workflow's ID, used as the idempotency key.
        from_account: Sending account ID.
        to_account: Receiving account ID.
        amount: Amount to move.
        new_location: The geolocated city/country/lat/lon for this transaction.
        new_at: ISO timestamp of this transaction.
    """
    try:
        return ledger_store.apply_transfer(
            workflow_id=workflow_id,
            from_account=from_account,
            to_account=to_account,
            amount=amount,
            new_location=new_location,
            new_at=new_at,
        )
    except ValueError as exc:
        raise ApplicationError(str(exc), non_retryable=True) from None
