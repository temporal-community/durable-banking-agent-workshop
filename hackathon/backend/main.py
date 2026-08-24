from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel

from fraud_check import IMPOSSIBLE_TRAVEL_SPEED_KMH, check_transfer_for_fraud
from geo import SPOOFABLE_LOCATIONS, geolocate_ip, haversine_km
from ledger import accounts, incidents, log_incident

FRONTEND_INDEX = Path(__file__).parent.parent / "frontend" / "index.html"

app = FastAPI(title="Ledger Bank - Hackathon Backend")


@app.get("/")
def frontend() -> FileResponse:
    # Served from the same origin as the API, so the frontend never needs a cross-origin fetch,
    # CORS config, or Instruqt's per-subdomain auth cookie at all - the network control panel's
    # own Flask app (docker/proxy/controlpanel.py) uses this same same-origin pattern.
    return FileResponse(FRONTEND_INDEX)


class TransferRequest(BaseModel):
    from_account: str
    to_account: str
    amount: float
    spoof_location: str | None = None


@app.get("/accounts/{account_id}")
def get_account(account_id: str) -> dict:
    account = accounts.get(account_id)
    if account is None:
        raise HTTPException(status_code=404, detail=f"no such account: {account_id}")
    return account


@app.get("/incidents")
def get_incidents() -> list[dict]:
    return incidents


@app.post("/transfer")
async def transfer(body: TransferRequest, request: Request) -> dict:
    if body.from_account not in accounts or body.to_account not in accounts:
        raise HTTPException(status_code=404, detail="unknown account")
    if body.amount <= 0:
        raise HTTPException(status_code=400, detail="amount must be positive")

    sender = accounts[body.from_account]
    if sender["balance"] < body.amount:
        raise HTTPException(status_code=400, detail="insufficient funds")

    if body.spoof_location:
        spoof_ip = SPOOFABLE_LOCATIONS.get(body.spoof_location)
        if spoof_ip is None:
            raise HTTPException(status_code=400, detail=f"unknown spoof location: {body.spoof_location}")
        ip = spoof_ip
    else:
        client_host = request.client.host if request.client else None
        # ip-api.com refuses loopback/private ranges, which is all a local dev run ever sees.
        ip = client_host if client_host and client_host not in ("127.0.0.1", "::1") else "8.8.8.8"

    # No retry, no timeout handling here on purpose - a flaky geo-IP call just fails the request.
    location = await geolocate_ip(ip)

    now = datetime.now(timezone.utc)
    last_location = sender["last_location"]
    last_at = sender["last_transaction_at"]
    distance_km = haversine_km(last_location["lat"], last_location["lon"], location["lat"], location["lon"])
    elapsed_hours = max((now - last_at).total_seconds() / 3600, 1e-6)
    implied_speed_kmh = distance_km / elapsed_hours

    decision = await check_transfer_for_fraud(
        home_country=sender["home_country"],
        last_city=last_location["city"],
        last_country=last_location["country"],
        last_at=last_at,
        new_city=location["city"],
        new_country=location["country"],
        new_at=now,
        distance_km=distance_km,
        elapsed_hours=elapsed_hours,
        implied_speed_kmh=implied_speed_kmh,
    )

    if not decision.approve:
        log_incident(
            {
                "from_account": body.from_account,
                "to_account": body.to_account,
                "amount": body.amount,
                "location": location,
                "implied_speed_kmh": implied_speed_kmh,
                "verdict": "declined-fraud",
                "reason": decision.reason,
                "at": now.isoformat(),
            }
        )
        raise HTTPException(status_code=403, detail=f"transfer declined: {decision.reason}")

    sender["balance"] -= body.amount
    accounts[body.to_account]["balance"] += body.amount
    sender["last_location"] = location
    sender["last_transaction_at"] = now

    log_incident(
        {
            "from_account": body.from_account,
            "to_account": body.to_account,
            "amount": body.amount,
            "location": location,
            "implied_speed_kmh": implied_speed_kmh,
            "verdict": "accepted",
            "reason": decision.reason,
            "at": now.isoformat(),
        }
    )

    return {
        "status": "accepted",
        "from_account": accounts[body.from_account],
        "to_account": accounts[body.to_account],
        "impossible_travel_threshold_kmh": IMPOSSIBLE_TRAVEL_SPEED_KMH,
    }
