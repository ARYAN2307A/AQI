import html

import folium
import streamlit as st
from streamlit_folium import st_folium
import plotly.graph_objects as go
import advice
import analysis
import data
import forecast
import news
from utils import POLLUTANTS, aqi_category

st.set_page_config(
    page_title="Air Quality Monitor",
    page_icon="🌫️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """<style>
.block-container{padding-top:1.5rem;max-width:1250px}
#MainMenu, footer{visibility:hidden}
.hero-title{font-size:2rem;font-weight:800;margin:0;line-height:1.2}
.hero-sub{opacity:.7;margin:.25rem 0 1rem}
.aqi-card{border-radius:18px;padding:20px 22px;color:#fff;box-shadow:0 4px 18px rgba(0,0,0,.25)}
.aqi-place{font-size:.95rem;opacity:.95;margin-bottom:6px}
.aqi-row{display:flex;align-items:baseline;gap:14px;flex-wrap:wrap}
.aqi-num{font-size:3.6rem;font-weight:800;line-height:1}
.aqi-label{font-size:1.35rem;font-weight:600}
.aqi-msg{margin:10px 0 14px;font-size:1rem;opacity:.95}
.scale{position:relative;height:10px;border-radius:6px;background:linear-gradient(90deg,#00a000 0 10%,#c9a400 10% 20%,#ff7e00 20% 30%,#e60000 30% 40%,#8f3f97 40% 60%,#7e0023 60% 100%);border:1px solid rgba(255,255,255,.55)}
.ptr{position:absolute;top:-6px;width:4px;height:22px;background:#fff;border-radius:3px;transform:translateX(-50%);box-shadow:0 0 0 2px rgba(0,0,0,.35)}
.aqi-meta{margin-top:12px;font-size:.8rem;opacity:.85}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:6px 0 10px}
.tile{border:1px solid rgba(128,128,128,.25);background:rgba(128,128,128,.08);border-radius:14px;padding:12px 14px}
.t-name{font-size:.85rem;opacity:.75;font-weight:600}
.t-val{font-size:1.7rem;font-weight:700;margin:2px 0 8px}
.t-val span{font-size:.75rem;font-weight:400;opacity:.65}
.bar{position:relative;height:7px;border-radius:5px;background:rgba(128,128,128,.28);overflow:hidden}
.bar>div{height:100%;border-radius:5px}
.bar::after{content:"";position:absolute;left:50%;top:0;width:2px;height:100%;background:rgba(255,255,255,.7)}
.t-sub{font-size:.78rem;margin-top:6px;font-weight:600}
.chip{display:inline-block;padding:3px 12px;border-radius:999px;font-size:.82rem;margin:0 6px 6px 0;background:rgba(128,128,128,.2)}
div[data-testid="stMetric"]{background:rgba(128,128,128,.08);border:1px solid rgba(128,128,128,.22);padding:10px 14px;border-radius:12px}
button[role="tab"]{font-weight:600}
@media (max-width:640px){.aqi-num{font-size:2.6rem}.hero-title{font-size:1.5rem}}
</style>""",
    unsafe_allow_html=True,
)

SUMMARY = {
    "Good": "The air is clean. A great time to be outside.",
    "Moderate": "Acceptable for most people. Very sensitive people may notice effects.",
    "Unhealthy for Sensitive Groups": "Sensitive groups should cut back on prolonged outdoor effort.",
    "Unhealthy": "Everyone may start to feel effects. Limit time outdoors.",
    "Very Unhealthy": "Health alert. Avoid outdoor exertion and stay indoors if you can.",
    "Hazardous": "Emergency conditions. Stay indoors with clean air.",
}
QUICK = {
    "Delhi": (28.6139, 77.2090, "Delhi, India"),
    "Mumbai": (19.0760, 72.8777, "Mumbai, Maharashtra, India"),
    "Chennai": (13.0827, 80.2707, "Chennai, Tamil Nadu, India"),
    "Kolkata": (22.5726, 88.3639, "Kolkata, West Bengal, India"),
    "London": (51.5072, -0.1276, "London, England, United Kingdom"),
    "Beijing": (39.9042, 116.4074, "Beijing, China"),
    "New York": (40.7128, -74.0060, "New York, United States"),
    "Reykjavik": (64.1466, -21.9426, "Reykjavik, Iceland"),
}


def hero_html(place, aqi, label, color, asof):
    shown = "500+" if aqi > 500 else f"{aqi:.0f}"
    pct = min(aqi, 500) / 500 * 100
    return (
        f'<div class="aqi-card" style="background:{color}">'
        f'<div class="aqi-place">📍 {html.escape(place)}</div>'
        f'<div class="aqi-row"><span class="aqi-num">{shown}</span>'
        f'<span class="aqi-label">{label}</span></div>'
        f'<div class="aqi-msg">{SUMMARY.get(label, "")}</div>'
        f'<div class="scale"><div class="ptr" style="left:{pct:.1f}%"></div></div>'
        f'<div class="aqi-meta">US AQI · data hour {asof}</div></div>'
    )


def tiles_html(latest):
    out = []
    for key, (name, limit) in POLLUTANTS.items():
        v = latest.get(key)
        if v is None or v != v:
            out.append(
                f'<div class="tile"><div class="t-name">{name}</div>'
                f'<div class="t-val">n/a</div></div>'
            )
            continue
        ratio = v / limit
        c = (
            "#00a000"
            if ratio <= 1
            else "#c9a400" if ratio <= 2 else "#ff7e00" if ratio <= 4 else "#e60000"
        )
        width = min(ratio, 2) / 2 * 100
        out.append(
            f'<div class="tile"><div class="t-name">{name}</div>'
            f'<div class="t-val">{v:.1f}<span> µg/m³</span></div>'
            f'<div class="bar"><div style="width:{width:.0f}%;background:{c}"></div></div>'
            f'<div class="t-sub" style="color:{c}">{ratio:.1f}× WHO guideline</div></div>'
        )
    return '<div class="tiles">' + "".join(out) + "</div>"
def city_ranking():
    """Latest AQI for every quick-pick city, cleanest first."""
    rows = []
    for name, (la, lo, _) in QUICK.items():
        d = data.fetch_air_quality(la, lo, 1)
        if d is None:
            continue
        s = d.dropna(subset=["us_aqi"])
        if not s.empty:
            rows.append((name, float(s.iloc[-1]["us_aqi"])))
    return sorted(rows, key=lambda r: r[1])


def ranking_chart(rows):
    vals = [r[1] for r in rows]
    fig = go.Figure(go.Bar(
        x=vals, y=[r[0] for r in rows], orientation="h",
        marker_color=[aqi_category(v)[1] for v in vals],
        text=[f"{v:.0f}" for v in vals], textposition="outside", cliponaxis=False))
    fig.update_layout(height=70 + 38 * len(rows), xaxis_title="US AQI (latest hour)",
                      yaxis=dict(autorange="reversed"), margin=dict(l=10, r=40, t=10, b=10))
    return fig

ss = st.session_state
ss.setdefault("lat", 28.6139)
ss.setdefault("lon", 77.2090)
ss.setdefault("place", "Delhi, India")
ss.setdefault("last_click", None)
ss.setdefault("last_search", None)
ss.setdefault("ranking", None)
# ======================= Sidebar =======================
st.sidebar.title("🌫️ Air Quality Monitor")
st.sidebar.caption("Pick a place, set a window, explore.")

query = st.sidebar.text_input("🔎 Search a city", placeholder="e.g. Mumbai, London")
if query:
    results = data.geocode_city(query)
    if results:
        idx = 0
        if len(results) > 1:
            names = [r["name"] for r in results]
            idx = names.index(st.sidebar.selectbox("Did you mean", names))
        key = (query, idx)
        if key != ss.last_search:
            ss.last_search = key
            r = results[idx]
            ss.lat, ss.lon, ss.place = r["lat"], r["lon"], r["name"]
    else:
        st.sidebar.warning("City not found. Try another spelling.")

st.sidebar.markdown("**Quick picks**")
qcols = st.sidebar.columns(2)
for i, (n, (la, lo, pl)) in enumerate(QUICK.items()):
    if qcols[i % 2].button(n, use_container_width=True, key=f"quick_{n}"):
        ss.lat, ss.lon, ss.place = la, lo, pl
        st.rerun()

days = st.sidebar.select_slider(
    "📅 Analysis window",
    options=[1, 3, 7, 14, 30, 90],
    value=14,
    format_func=lambda d: "24 hours" if d == 1 else f"{d} days",
)
pollutant = st.sidebar.selectbox(
    "🧪 Pollutant (Trends tab)",
    list(POLLUTANTS),
    format_func=lambda k: POLLUTANTS[k][0],
)
st.sidebar.divider()
st.sidebar.caption(f"📍 {ss.place}\n\nLat {ss.lat:.3f} · Lon {ss.lon:.3f}")
with st.sidebar.expander("About this app"):
    st.markdown(
        "- **Data:** Open-Meteo / CAMS model estimates, not raw station readings\n"
        "- **Forecast:** LightGBM, validated chronologically against a same-hour-yesterday baseline\n"
        "- **News:** public media headlines, not official findings\n"
        "- **Advice:** general guidance, not medical advice"
    )

# ======================= Header =======================
st.markdown(
    '<p class="hero-title">🌫️ Real-Time Air Quality Monitoring &amp; Prediction</p>'
    '<p class="hero-sub">Click the map or search a city to analyse any region: '
    "current conditions, trends, a 48-hour forecast, news and advice.</p>",
    unsafe_allow_html=True,
)

with st.spinner("Fetching air quality data..."):
    df = data.fetch_air_quality(ss.lat, ss.lon, days)

latest = aqi = label = color = None
if df is not None:
    latest = df.dropna(subset=["us_aqi"]).iloc[-1]
    aqi = float(latest["us_aqi"])
    label, color = aqi_category(aqi)

# ======================= Map + hero =======================
left, right = st.columns([3, 2], gap="large")
with left:
    m = folium.Map(location=[ss.lat, ss.lon], zoom_start=6, tiles="OpenStreetMap")
    folium.CircleMarker(
        [ss.lat, ss.lon],
        radius=11,
        color="#ffffff",
        weight=2,
        fill=True,
        fill_color=color or "#4f8df5",
        fill_opacity=0.95,
        tooltip=ss.place,
    ).add_to(m)
    out = st_folium(
        m, height=340, use_container_width=True, returned_objects=["last_clicked"]
    )
    st.caption("💡 Click anywhere on the map to analyse that spot.")
    click = out.get("last_clicked") if out else None
    if click:
        ck = (round(click["lat"], 4), round(click["lng"], 4))
        if ck != ss.last_click:
            ss.last_click = ck
            ss.lat, ss.lon = click["lat"], click["lng"]
            ss.place = data.reverse_geocode(ss.lat, ss.lon)
            st.rerun()
with right:
    if df is None:
        st.error(
            "**No data for this spot.**\n\nThe data source didn't return anything here. "
            "Try a nearby point, a larger city, or check your internet connection."
        )
    else:
        st.markdown(
            hero_html(ss.place, aqi, label, color, f"{latest.name:%d %b, %H:%M} local"),
            unsafe_allow_html=True,
        )
        dom = advice.dominant_pollutant(latest)
        chips = ""
        if dom:
            chips += f'<span class="chip">Main concern: <b>{dom[1]}</b> ({dom[2]:.1f}× WHO)</span>'
        if advice.is_dust(latest):
            chips += '<span class="chip">🏜️ Likely dust event</span>'
        if chips:
            st.markdown(
                f'<div style="margin-top:12px">{chips}</div>', unsafe_allow_html=True
            )

if df is None:
    st.stop()

# ======================= Tabs =======================
tab_over, tab_trend, tab_fc, tab_news, tab_rec = st.tabs(
    [
        "📊 Overview",
        "📈 Trends",
        "🔮 Forecast",
        "📰 Environmental & Compliance",
        "💡 Recommendations",
    ]
)

# ---------- Overview ----------
with tab_over:
    st.markdown("##### Pollutants right now")
    st.markdown(tiles_html(latest), unsafe_allow_html=True)
    st.caption(
        "The white marker on each bar is the WHO 24-hour guideline; the bar's end is 2× the guideline. "
        "Data: Open-Meteo (CAMS model-based estimates on a ~11 km grid, not raw ground-station readings)."
    )
    with st.expander("How to read this"):
        st.markdown(
            "- **AQI** (US scale) runs 0-500: green is good, red is unhealthy, purple and maroon are dangerous.\n"
            "- **WHO guideline** values are health-based 24-hour targets. Exceeding them does not mean "
            "immediate harm, but long-term exposure above them raises health risks.\n"
            "- **PM2.5 / PM10** are fine and coarse particles. A PM10 much higher than PM2.5 usually means dust."
        )

        pm24 = df["pm2_5"].dropna().tail(24)
    if len(pm24) >= 12:
        cigs = pm24.mean() / 22
        st.markdown("##### 🚬 Cigarette equivalent")
        k1, k2 = st.columns([1, 2])
        k1.metric("Last 24 hours", f"≈ {cigs:.1f} cigarettes")
        k2.caption("A popular rule of thumb (Berkeley Earth): a day at about 22 µg/m³ of PM2.5 is "
                   "comparable to smoking one cigarette. This is a rough communication aid, not a medical "
                   "measurement, and it overstates harm in dust-dominated air, where coarse mineral "
                   "particles are less toxic than combustion particles.")

        st.markdown("##### 🏆 City ranking")
    if st.button("Load live ranking of the quick-pick cities"):
        with st.spinner("Fetching latest air quality for each city..."):
            ss.ranking = city_ranking()
    if ss.ranking:
        st.plotly_chart(ranking_chart(ss.ranking), use_container_width=True)
        st.caption("Cleanest at the top. Latest available hour; CAMS model estimates, so values may differ "
                   "from local station readings.")
# ---------- Trends ----------
with tab_trend:
    pname, who = POLLUTANTS[pollutant]
    series = df[pollutant].dropna()
    if series.empty:
        st.warning(f"No {pname} data available for this location and window.")
    else:
        over, total = analysis.exceedance(df, pollutant, who)
        tr = analysis.trend(df, pollutant)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric(f"Average {pname}", f"{series.mean():.1f} µg/m³")
        c2.metric(
            "Peak",
            f"{series.max():.1f} µg/m³",
            f"{series.idxmax():%d %b, %H:%M}",
            delta_color="off",
        )
        c3.metric("Days over WHO guideline", f"{over} / {total}")
        c4.metric(
            "Trend",
            tr["direction"] if tr else "Need 5+ days",
            f"{tr['rel'] * 100:+.0f}% over window" if tr else None,
            delta_color="off",
        )

        st.markdown(
            f"##### {pname} over the last {'24 hours' if days == 1 else f'{days} days'}"
        )
        st.plotly_chart(
            analysis.line_chart(df, pollutant, pname, who), use_container_width=True
        )

        st.markdown("##### Daily averages")
        st.plotly_chart(
            analysis.daily_bar_chart(df, pollutant, pname, who),
            use_container_width=True,
        )
        st.caption("Red bars exceed the WHO 24-hour guideline.")

        cl, cr = st.columns(2)
        with cl:
            st.markdown("##### Typical day (hour-of-day)")
            st.plotly_chart(
                analysis.hourly_chart(df, pollutant, pname), use_container_width=True
            )
        with cr:
            st.markdown("##### Weekday pattern")
            if days >= 7:
                st.plotly_chart(
                    analysis.weekday_chart(df, pollutant, pname),
                    use_container_width=True,
                )
            else:
                st.info("Choose a window of 7+ days to see weekday patterns.")
        
                st.markdown("##### Heatmap: day × hour")
        if days >= 2:
            st.plotly_chart(analysis.heatmap_chart(df, pollutant, pname), use_container_width=True)
            st.caption("Darker cells mean higher concentrations. Look for repeating dark bands "
                       "at the same hours (rush hour, nightly inversions) and for single bad days.")
        else:
            st.info("Choose a window of 2+ days to see the heatmap.")

        st.download_button(
            "⬇️ Download data as CSV",
            df.to_csv().encode("utf-8"),
            file_name=f"air_quality_{ss.lat:.2f}_{ss.lon:.2f}.csv",
            mime="text/csv",
        )

# ---------- Forecast ----------
with tab_fc:
    with st.spinner(
        "Training the forecast model (first run per location takes a few seconds)..."
    ):
        res = forecast.run_forecast(ss.lat, ss.lon)
    if not res["ok"]:
        st.warning(
            f"{res['error']}\n\nTry a location with more history, such as a larger city."
        )
    else:
        m1, m2 = res["metrics"]["d1"], res["metrics"]["d2"]
        imp_pct = (
            ((m1["base_mae"] - m1["model_mae"]) / m1["base_mae"] * 100)
            if m1["base_mae"]
            else 0
        )
        if imp_pct >= 5:
            st.success(
                f"✅ Over the next 24 h, the model is about {imp_pct:.0f}% more accurate than "
                "the 'same hour yesterday' baseline on held-out data."
            )
        elif imp_pct > -5:
            st.info(
                "ℹ️ At this location the model performs about the same as the "
                "'same hour yesterday' baseline."
            )
        else:
            st.warning(
                "⚠️ At this location the simple baseline is more accurate than the model, "
                "so treat this forecast as indicative only."
            )

        i = int(res["pred"].argmax())
        c1, c2, c3, c4 = st.columns(4)
        c1.metric(
            "Model error, next 24h (MAE)",
            f"{m1['model_mae']:.1f} µg/m³",
            f"{-imp_pct:+.0f}% vs baseline",
            delta_color="inverse",
        )
        c2.metric("Baseline error", f"{m1['base_mae']:.1f} µg/m³")
        c3.metric(
            "Model RMSE, next 24h",
            f"{m1['model_rmse']:.1f} µg/m³",
            f"baseline {m1['base_rmse']:.1f}",
            delta_color="off",
        )
        c4.metric(
            "Predicted peak (48h)",
            f"{res['pred'][i]:.0f} µg/m³",
            f"{res['times'][i]:%a %H:%M}",
            delta_color="off",
        )

        st.markdown("##### 48-hour PM2.5 forecast")
        st.plotly_chart(forecast.forecast_chart(res), use_container_width=True)

        win = forecast.best_outdoor_window(res)
        if win:
            st.success(
                f"🌿 Best time outdoors tomorrow: **{win['start']:%H:%M}-{win['end']:%H:%M}** "
                f"(predicted PM2.5 ≈ {win['mean']:.0f} µg/m³ vs. daytime average {win['day_mean']:.0f})"
            )

        cl, cr = st.columns(2)
        with cl:
            st.markdown("##### Error by forecast horizon")
            st.plotly_chart(forecast.error_chart(res), use_container_width=True)
        with cr:
            st.markdown("##### What drives the forecast")
            st.plotly_chart(forecast.importance_chart(res), use_container_width=True)

        with st.expander("How was this evaluated?"):
            st.markdown(
                f"- Trained only on earlier data; tested on **{res['n_origins']} forecasts** from the held-out "
                f"final {res['test_days']:.0f} days (chronological split, no shuffling).\n"
                f"- Day 2 (25-48 h): model MAE {m2['model_mae']:.1f} vs baseline {m2['base_mae']:.1f} µg/m³.\n"
                "- Test forecasts use observed weather, while live forecasts use forecast weather, so real-world "
                "error can be somewhat higher.\n"
                "- The shaded band is an approximate 80% interval from test errors. The red dashed CAMS line is "
                "the data provider's own forecast, shown for reference."
            )

# ---------- News ----------
with tab_news:
    st.markdown("##### Publicly reported environmental & air-quality issues")
    st.caption(
        "Headlines from public news sources. These are media reports, not official findings, "
        "and relevance varies by location. Always open the source to verify."
    )
    with st.spinner("Searching public news..."):
        items, scope, status = news.fetch_news(ss.place)
    if status == "ok":
        st.write(f"Showing results for **{scope}**")
        for it in items:
            with st.container(border=True):
                st.markdown(f"**[{it['title']}]({it['link']})**")
                st.caption(f"{it['source']} · {it['date']} · {it['tag']}")
    elif status == "none":
        st.info(
            f"No publicly reported issues found for '{scope}' in the last two years. "
            "This does not mean none exist. Check the local pollution-control board "
            "or environmental regulator for official records."
        )
    else:
        st.warning(
            "Could not reach the news sources from this network, so no result can be shown. "
            "This is a connection problem, not an absence of news. Try again later, or search manually:"
        )
    if status != "ok":
        st.markdown(" · ".join(f"[{n}]({u})" for n, u in news.search_links(ss.place)))
    st.caption(
        "For official records, consult the local pollution-control board or environmental regulator."
    )

# ---------- Recommendations ----------
with tab_rec:
    win_r = forecast.best_outdoor_window(res) if res["ok"] else None
    adv = advice.build_advice(latest, aqi, res if res["ok"] else None, win_r)
    st.markdown(
        f"##### Current air quality: **{adv['label']}** (AQI {'500+' if aqi > 500 else f'{aqi:.0f}'})"
    )

    def bullets(items):
        st.markdown("\n".join(f"- {x}" for x in items))

    c1, c2 = st.columns(2)
    with c1:
        with st.container(border=True):
            st.markdown("#### 🧍 Personal exposure")
            bullets(adv["personal"])
    with c2:
        with st.container(border=True):
            st.markdown("#### 🧒 Sensitive groups")
            bullets(adv["sensitive"])
    with st.container(border=True):
        st.markdown("#### 🏙️ Community & policy actions")
        bullets(adv["community"])
    if adv["forecast"]:
        with st.container(border=True):
            st.markdown("#### 🔮 Based on the forecast")
            bullets(adv["forecast"])
    st.caption(
        "General guidance based on common public-health recommendations. It is not medical advice."
    )

st.divider()
st.caption(
    "Built with Streamlit · Data: Open-Meteo (CAMS), OpenStreetMap Nominatim, public news RSS/APIs · "
    "Forecasts are estimates and can be wrong."
)
