"""Rule-based recommendations from AQI band, dominant pollutant and the forecast."""
from utils import POLLUTANTS, aqi_category

PERSONAL = {
    "Good": ["Air quality is good. Enjoy outdoor activity as normal."],
    "Moderate": ["Fine for most people. Unusually sensitive people may want shorter, "
                 "less intense outdoor sessions."],
    "Unhealthy for Sensitive Groups": [
        "Reduce prolonged or heavy outdoor exertion.",
        "Move hard workouts indoors or to the cleanest hours of the day.",
        "Keep windows closed during the worst hours."],
    "Unhealthy": [
        "Avoid prolonged outdoor exertion and move workouts indoors.",
        "Wear a well-fitted N95/FFP2 respirator for extended time outside.",
        "Run an air purifier with a HEPA filter indoors if you have one."],
    "Very Unhealthy": [
        "Stay indoors as much as possible with windows and doors closed.",
        "If you must go out, wear an N95/FFP2 respirator. Cloth and surgical masks "
        "give little protection from fine particles.",
        "Use a HEPA purifier and keep one 'clean room' (e.g. the bedroom)."],
    "Hazardous": [
        "Avoid going outside. Postpone non-essential outdoor activity.",
        "Keep windows sealed, use a HEPA purifier, and wear an N95/FFP2 if you must go out.",
        "Seek medical care for breathing difficulty, chest pain or severe coughing."],
}
SENSITIVE_LOW = ["Children, older adults, pregnant people and people with asthma or heart/lung "
                 "disease: watch for symptoms and keep prescribed medication accessible."]
SENSITIVE_HIGH = [
    "Children, older adults, pregnant people and people with asthma, COPD or heart disease "
    "should avoid outdoor exertion.",
    "Keep prescribed inhalers or medication within reach and follow your doctor's action plan.",
    "Schools and workplaces: move sports and strenuous activity indoors."]

POLLUTANT_TIPS = {
    "pm": ["Fine particles get indoors: seal gaps, use a HEPA purifier, and avoid indoor "
           "smoke sources (incense, candles, poorly ventilated frying).",
           "Avoid exercising near busy roads."],
    "dust": ["Dust event likely (coarse PM10 far exceeds PM2.5): keep windows shut, "
             "wet-mop instead of dry sweeping, protect your eyes, and use N95/FFP2 outdoors."],
    "nitrogen_dioxide": ["NO₂ comes mostly from vehicle exhaust: avoid walking or cycling "
                         "along busy roads and at rush hour; prefer parks and side streets."],
    "ozone": ["Ozone peaks in the afternoon: schedule outdoor activity for morning or evening."],
    "sulphur_dioxide": ["SO₂ is typically industrial or volcanic: people with asthma are "
                        "especially sensitive, so stay away from industrial areas."],
    "carbon_monoxide": ["Make sure fuel-burning appliances are vented, never run engines or "
                        "generators in enclosed spaces, and consider a CO alarm."],
}
COMMUNITY_BASE = [
    "Use public transport, carpool, cycle or walk for short trips.",
    "Avoid burning waste, leaves or biomass, and report open burning to local authorities.",
    "Report visible industrial smoke or construction dust to the local pollution-control authority."]
COMMUNITY = {
    "pm": ["Cut vehicle idling and support dust suppression on roads and construction sites."],
    "dust": ["Support dust control: windbreaks, vegetation, covering exposed soil, water spraying."],
    "nitrogen_dioxide": ["Support low-traffic zones, better signal timing and electric vehicles."],
    "ozone": ["Reducing NOx and VOC emissions (vehicles, solvents, fuel vapour) lowers ozone."],
    "sulphur_dioxide": ["Support emission controls at industrial and power sources and public "
                        "stack-monitoring data."],
    "carbon_monoxide": ["Promote clean cooking and heating and well-ventilated housing."],
}


def dominant_pollutant(latest):
    """Pollutant with the highest concentration relative to its WHO guideline."""
    best = None
    for key, (name, limit) in POLLUTANTS.items():
        v = latest.get(key)
        if v is None or v != v:
            continue
        ratio = v / limit
        if best is None or ratio > best[2]:
            best = (key, name, ratio)
    return best


def is_dust(latest) -> bool:
    p10, p25 = latest.get("pm10"), latest.get("pm2_5")
    if p10 is None or p25 is None or p10 != p10 or p25 != p25 or p25 <= 0:
        return False
    return p10 >= 100 and p10 / p25 >= 3


def build_advice(latest, aqi: float, res=None, win=None) -> dict:
    label, _ = aqi_category(aqi)
    dom = dominant_pollutant(latest)
    dust = is_dust(latest)
    key = "dust" if dust else None
    if key is None and dom:
        key = "pm" if dom[0] in ("pm2_5", "pm10") else dom[0]

    personal = list(PERSONAL.get(label, []))
    community = list(COMMUNITY_BASE)
    if key and label != "Good":
        personal += POLLUTANT_TIPS.get(key, [])
    if key:
        community += COMMUNITY.get(key, [])
    sensitive = SENSITIVE_HIGH if label not in ("Good", "Moderate", "Unknown") else SENSITIVE_LOW

    fc = []
    if res and res.get("ok"):
        i = int(res["pred"].argmax())
        fc.append(f"Forecast PM2.5 peaks around {res['times'][i]:%a %H:%M} "
                  f"(≈{res['pred'][i]:.0f} µg/m³). Plan outdoor activity away from that window.")
        if win:
            fc.append(f"Best time outdoors tomorrow: {win['start']:%H:%M}–{win['end']:%H:%M} "
                      f"(predicted PM2.5 ≈ {win['mean']:.0f} µg/m³).")
    return {"label": label, "dominant": dom, "dust": dust, "personal": personal,
            "sensitive": sensitive, "community": community, "forecast": fc}