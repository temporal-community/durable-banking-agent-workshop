from __future__ import annotations

from datetime import datetime

from agents import Agent, Runner, function_tool
from pydantic import BaseModel

IMPOSSIBLE_TRAVEL_SPEED_KMH = 900.0

INSTRUCTIONS = f"""
You are a fraud investigator for a bank. Use the provided tools to gather the account's home
country and its travel facts since the last transaction, then decide whether to approve or
decline this transfer.

Impossible travel means the implied speed between the last known location and the new one
exceeds {IMPOSSIBLE_TRAVEL_SPEED_KMH:.0f} km/h, the cruising speed of a commercial flight - no
traveler could plausibly cover that distance in that time. Decline only when the travel is
genuinely implausible; a short trip abroad is not fraud on its own.
"""


class FraudDecision(BaseModel):
    approve: bool
    reason: str


class TravelFacts(BaseModel):
    home_country: str
    last_city: str
    last_country: str
    last_transaction_at: str
    new_city: str
    new_country: str
    new_transaction_at: str
    distance_km: float
    elapsed_hours: float
    implied_speed_kmh: float


def build_fraud_check_agent(facts: TravelFacts) -> Agent:
    @function_tool
    def get_account_home_country() -> str:
        """Get the home country registered for this account."""
        return facts.home_country

    @function_tool
    def get_last_transaction_location() -> str:
        """Get the city, country and timestamp of the account's last transaction."""
        return f"{facts.last_city}, {facts.last_country} at {facts.last_transaction_at}"

    @function_tool
    def get_current_transaction_location() -> str:
        """Get the city, country and timestamp of this transaction request."""
        return f"{facts.new_city}, {facts.new_country} at {facts.new_transaction_at}"

    @function_tool
    def get_travel_speed_since_last_transaction() -> str:
        """Get the distance, elapsed time and implied travel speed since the last transaction."""
        return (
            f"{facts.distance_km:.0f} km in {facts.elapsed_hours:.2f} hours, "
            f"implying {facts.implied_speed_kmh:.0f} km/h"
        )

    return Agent(
        name="FraudInvestigator",
        instructions=INSTRUCTIONS,
        model="gpt-4o",
        tools=[
            get_account_home_country,
            get_last_transaction_location,
            get_current_transaction_location,
            get_travel_speed_since_last_transaction,
        ],
        output_type=FraudDecision,
    )


async def check_transfer_for_fraud(
    *,
    home_country: str,
    last_city: str,
    last_country: str,
    last_at: datetime,
    new_city: str,
    new_country: str,
    new_at: datetime,
    distance_km: float,
    elapsed_hours: float,
    implied_speed_kmh: float,
) -> FraudDecision:
    """Ask the fraud-check agent to approve or decline a transfer given its travel facts."""
    facts = TravelFacts(
        home_country=home_country,
        last_city=last_city,
        last_country=last_country,
        last_transaction_at=last_at.isoformat(),
        new_city=new_city,
        new_country=new_country,
        new_transaction_at=new_at.isoformat(),
        distance_km=distance_km,
        elapsed_hours=elapsed_hours,
        implied_speed_kmh=implied_speed_kmh,
    )
    agent = build_fraud_check_agent(facts)
    result = await Runner.run(agent, input="Decide whether to approve this transfer.")
    return result.final_output_as(FraudDecision)
