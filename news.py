"""Publicly reported pollution / compliance news with multiple fallback sources."""

import time
import re
from urllib.parse import parse_qs, quote_plus, urlencode, urlparse

import feedparser
import requests
import streamlit as st

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; AirQualityMonitor/1.0; club project)"
}
POLLUTION_KW = [
    "pollut",
    "air quality",
    "aqi",
    "emission",
    "smog",
    "haze",
    "dust storm",
    "particulate",
    "pm2.5",
    "pm10",
    "toxic",
    "fumes",
    "stubble",
    "pollution control",
    "tribunal",
]
COMPLIANCE_KW = [
    "violation",
    "violat",
    "fine",
    "fined",
    "penalt",
    "notice",
    "tribunal",
    "court",
    "closure",
    "shut",
    "ban",
    "norms",
    "compliance",
    "illegal",
    "lawsuit",
    "sanction",
    "crackdown",
    "ngt",
    "epa",
]
# short or ambiguous terms must match as whole words
_WORD_ONLY = {"fine", "ban", "ngt", "epa", "aqi"}

BLOCKED_SOURCES = ("iqair", "facebook", "aqi.in", "twitter", "instagram", "youtube")


def _has(text: str, kws) -> bool:
    for k in kws:
        if k in _WORD_ONLY:
            if re.search(rf"\b{k}\b", text):
                return True
        elif k in text:
            return True
    return False


class SourceError(Exception):
    """A news source could not be reached (never cached)."""


def _get(url, params=None):
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=8)
        r.raise_for_status()
        return r
    except requests.RequestException as e:
        raise SourceError(str(e))


def _raw(title, source, link, ts):
    return {
        "title": title.strip(),
        "source": source or "Unknown source",
        "link": link,
        "ts": ts or 0,
    }


# ------------------------------------------------------------------ sources
@st.cache_data(ttl=3600, show_spinner=False)
def _google(term: str) -> list[dict]:
    q = (
        f'"{term}" (air pollution OR emissions OR "air quality" OR violation OR '
        f'"pollution control" OR tribunal OR fine) when:2y'
    )
    r = _get(
        "https://news.google.com/rss/search",
        {"q": q, "hl": "en", "gl": "US", "ceid": "US:en"},
    )
    out = []
    for e in feedparser.parse(r.content).entries:
        title = e.get("title", "")
        src = (e.get("source") or {}).get("title", "")
        if src and title.endswith(" - " + src):
            title = title[: -len(" - " + src)]
        p = e.get("published_parsed")
        out.append(_raw(title, src, e.get("link", ""), time.mktime(p) if p else 0))
    return out


@st.cache_data(ttl=3600, show_spinner=False)
def _bing(term: str) -> list[dict]:
    q = f'{term} air pollution OR emissions OR "pollution control" OR violation'
    r = _get("https://www.bing.com/news/search", {"q": q, "format": "RSS"})
    out = []
    for e in feedparser.parse(r.content).entries:
        link = e.get("link", "")
        real = parse_qs(urlparse(link).query).get("url")
        if real:
            link = real[0]
        p = e.get("published_parsed")
        out.append(
            _raw(
                e.get("title", ""),
                e.get("news_source", ""),
                link,
                time.mktime(p) if p else 0,
            )
        )
    return out


@st.cache_data(ttl=3600, show_spinner=False)
def _gdelt(term: str) -> list[dict]:
    r = _get(
        "https://api.gdeltproject.org/api/v2/doc/doc",
        {
            "query": f'"{term}" (pollution OR "air quality" OR emissions) sourcelang:english',
            "mode": "artlist",
            "maxrecords": 25,
            "format": "json",
            "timespan": "24months",
            "sort": "datedesc",
        },
    )
    try:
        arts = r.json().get("articles", [])
    except ValueError:
        raise SourceError("GDELT returned a non-JSON response (rate limited?)")
    out = []
    for a in arts:
        try:
            ts = time.mktime(time.strptime(a["seendate"], "%Y%m%dT%H%M%SZ"))
        except (KeyError, ValueError):
            ts = 0
        out.append(_raw(a.get("title", ""), a.get("domain", ""), a.get("url", ""), ts))
    return out


SOURCES = [_google, _bing, _gdelt]


# ------------------------------------------------------------------ cleaning
def _clean(raw: list[dict], term: str) -> list[dict]:
    items, seen = [], set()
    t = term.lower()
    for it in sorted(raw, key=lambda x: -x["ts"]):
        low = it["title"].lower()
        if not it["title"] or not it["link"]:
            continue
        if any(
            b in it["source"].lower() or b in it["link"].lower()
            for b in BLOCKED_SOURCES
        ):
            continue
        if "noise" in low:
            continue
        if "aqi) today" in low or "real-time" in low:
            continue
        if t not in low or not _has(low, POLLUTION_KW + ["aqi"]):
            continue
        key = low[:60]
        if key in seen:
            continue
        seen.add(key)
        items.append(
            {
                **it,
                "title": it["title"].replace("[", "(").replace("]", ")"),
                "date": (
                    time.strftime("%d %b %Y", time.localtime(it["ts"]))
                    if it["ts"]
                    else "date n/a"
                ),
                "tag": (
                    "Compliance / regulatory"
                    if _has(low, COMPLIANCE_KW)
                    else "Air quality news"
                ),
            }
        )
    return items


def fetch_news(place: str, limit: int = 8):
    """Return (items, scope, status). status: 'ok' | 'none' | 'unreachable'."""
    parts = [p.strip() for p in place.split(",") if p.strip()]
    candidates = [parts[0]] if parts else [place]
    if len(parts) >= 3:
        candidates.append(parts[1])  # state/region fallback
    reached = False
    for term in candidates:
        for source in SOURCES:
            try:
                raw = source(term)
                reached = True
            except SourceError:
                continue
            items = _clean(raw, term)
            if items:
                return items[:limit], term, "ok"
    return [], candidates[0], ("none" if reached else "unreachable")


def search_links(place: str) -> list[tuple[str, str]]:
    """Manual search links the user can open themselves."""
    q = quote_plus(f"{place} air pollution violation notice")
    return [
        ("Google News", f"https://news.google.com/search?q={q}"),
        ("Google search", f"https://www.google.com/search?q={q}"),
        ("Bing News", f"https://www.bing.com/news/search?q={q}"),
    ]
