from __future__ import annotations

from datetime import datetime, timezone

HOME_LOCATIONS = {
    "A": {"city": "New York", "country": "United States", "lat": 40.7128, "lon": -74.0060},
    "B": {"city": "London", "country": "United Kingdom", "lat": 51.5074, "lon": -0.1278},
}

accounts: dict[str, dict] = {
    "A": {
        "balance": 5000.0,
        "home_country": "United States",
        "last_location": HOME_LOCATIONS["A"],
        "last_transaction_at": datetime.now(timezone.utc),
    },
    "B": {
        "balance": 3000.0,
        "home_country": "United Kingdom",
        "last_location": HOME_LOCATIONS["B"],
        "last_transaction_at": datetime.now(timezone.utc),
    },
}

incidents: list[dict] = []

MAX_INCIDENTS = 20


def log_incident(entry: dict) -> None:
    incidents.append(entry)
    del incidents[:-MAX_INCIDENTS]
