import time
from datetime import datetime, timedelta, timezone

import pandas as pd
import requests
import streamlit as st

HEADERS = {"User-Agent": "AirQualityMonitor/1.0 (club recruitment project)"}
TIMEOUT = 10
AQ_VARS = ["pm10", "pm2_5", "carbon_monoxide", "nitrogen_dioxide",
           "sulphur_dioxide", "ozone", "us_aqi"]


def _get_json(url, params=None, retries=2):
    for i in range(retries + 1):
        try:
            r = requests.get(url, params=params, headers=HEADERS, timeout=TIMEOUT)
            r.raise_for_status()
            return r.json()
        except (requests.RequestException, ValueError):
            if i == retries:
                return None
            time.sleep(1)


@st.cache_data(ttl=3600, show_spinner=False)
def geocode_city(query: str):
    js = _get_json("https://geocoding-api.open-meteo.com/v1/search",
                   {"name": query, "count": 5})
    if not js or "results" not in js:
        return []
    return [
        {
            "name": ", ".join(p for p in [r.get("name"), r.get("admin1"), r.get("country")] if p),
            "lat": r["latitude"],
            "lon": r["longitude"],
        }
        for r in js["results"]
    ]


@st.cache_data(ttl=86400, show_spinner=False)
def reverse_geocode(lat: float, lon: float) -> str:
    time.sleep(1)  # Nominatim: max 1 request/second
    js = _get_json("https://nominatim.openstreetmap.org/reverse",
                   {"lat": round(lat, 4), "lon": round(lon, 4),
                    "format": "jsonv2", "zoom": 10})
    if not js or "address" not in js:
        return f"{lat:.2f}, {lon:.2f}"
    a = js["address"]
    local = (a.get("city") or a.get("town") or a.get("village")
             or a.get("county") or a.get("state_district"))
    parts = [local, a.get("state"), a.get("country")]
    return ", ".join(p for p in parts if p) or f"{lat:.2f}, {lon:.2f}"


@st.cache_data(ttl=1800, show_spinner=False)
def fetch_air_quality(lat: float, lon: float, past_days: int = 14):
    """Hourly air quality up to the current local hour. Returns DataFrame or None."""
    js = _get_json("https://air-quality-api.open-meteo.com/v1/air-quality", {
        "latitude": round(lat, 3), "longitude": round(lon, 3),
        "hourly": ",".join(AQ_VARS),
        "past_days": min(past_days, 92), "forecast_days": 1, "timezone": "auto",
    })
    if not js or "hourly" not in js:
        return None
    df = pd.DataFrame(js["hourly"])
    df["time"] = pd.to_datetime(df["time"])
    df = df.set_index("time").sort_index()
    df = df.interpolate(method="time", limit=3, limit_area="inside")
    offset = js.get("utc_offset_seconds", 0)
    now_local = (datetime.now(timezone.utc) + timedelta(seconds=offset)).replace(tzinfo=None)
    df = df[df.index <= now_local]
    return df if not df.dropna(subset=["us_aqi"]).empty else None