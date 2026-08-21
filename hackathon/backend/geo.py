from __future__ import annotations

from math import asin, cos, radians, sin, sqrt

import httpx

# Representative public IPs for each city offered by the frontend's spoof-location dropdown.
# ip-api.com geolocates by IP, not by city name, so this stands in for "the request came from X".
SPOOFABLE_LOCATIONS: dict[str, str] = {
    "New York": "8.8.8.8",
    "London": "185.86.151.11",
    "Tokyo": "133.242.0.3",
    "Lagos": "105.112.0.1",
    "Sydney": "1.1.1.1",
}

EARTH_RADIUS_KM = 6371.0


async def geolocate_ip(ip: str) -> dict:
    """Look up city, country, latitude and longitude for a public IP via ip-api.com."""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"http://ip-api.com/json/{ip}", timeout=5.0)
        response.raise_for_status()
        data = response.json()
        if data.get("status") != "success":
            raise RuntimeError(f"geolocation failed for {ip}: {data}")
        return {
            "city": data["city"],
            "country": data["country"],
            "lat": data["lat"],
            "lon": data["lon"],
        }


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in kilometers between two lat/lon points."""
    lat1, lon1, lat2, lon2 = map(radians, (lat1, lon1, lat2, lon2))
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * asin(sqrt(a))
