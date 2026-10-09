import math

BANDS = [
    (50, "Good", "#00a000"),
    (100, "Moderate", "#c9a400"),
    (150, "Unhealthy for Sensitive Groups", "#ff7e00"),
    (200, "Unhealthy", "#e60000"),
    (300, "Very Unhealthy", "#8f3f97"),
    (10_000, "Hazardous", "#7e0023"),
]

# column -> (label, WHO 2021 24h guideline in ug/m3)
POLLUTANTS = {
    "pm2_5": ("PM2.5", 15),
    "pm10": ("PM10", 45),
    "nitrogen_dioxide": ("NO₂", 25),
    "ozone": ("O₃", 100),
    "sulphur_dioxide": ("SO₂", 40),
    "carbon_monoxide": ("CO", 4000),
}


def aqi_category(aqi):
    """Return (label, color) for a US AQI value."""
    if aqi is None or (isinstance(aqi, float) and math.isnan(aqi)):
        return "Unknown", "#888888"
    for limit, label, color in BANDS:
        if aqi <= limit:
            return label, color
    return "Hazardous", "#7e0023"