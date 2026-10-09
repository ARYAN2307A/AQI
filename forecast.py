"""PM2.5 forecasting: LightGBM, recursive 48h forecast, honest baseline comparison."""
from datetime import datetime, timedelta, timezone

import lightgbm as lgb
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from data import _get_json

AQ_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
WX_URL = "https://api.open-meteo.com/v1/forecast"
WX_VARS = ["temperature_2m", "relative_humidity_2m", "wind_speed_10m",
           "wind_direction_10m", "precipitation"]
HISTORY_DAYS = 90          # fixed training history, independent of the sidebar window
H = 48                     # forecast horizon (hours)
MIN_HOURS = 30 * 24        # minimum history needed to train and evaluate
LAGS = [1, 2, 3, 6, 12, 24]
EXOG = ["hour_sin", "hour_cos", "dow", "temp", "humidity", "wind_speed",
        "wind_dir_sin", "wind_dir_cos", "precip"]
FEATURES = ["lvl_24", "lvl_1", "d1", "d3", "d6", "d24", "slope_3", "std_24"] + EXOG
HOUR = pd.Timedelta(hours=1)


# ---------------------------------------------------------------- data
@st.cache_data(ttl=1800, show_spinner=False)
def fetch_inputs(lat: float, lon: float):
    """90 days of PM2.5 + weather, plus 4 forecast days. Returns (df, now_local) or None."""
    common = {"latitude": lat, "longitude": lon, "past_days": HISTORY_DAYS,
              "forecast_days": 4, "timezone": "auto"}
    aq = _get_json(AQ_URL, {**common, "hourly": "pm2_5"})
    wx = _get_json(WX_URL, {**common, "hourly": ",".join(WX_VARS)})
    if not aq or "hourly" not in aq or not wx or "hourly" not in wx:
        return None
    frames = []
    for js in (aq, wx):
        f = pd.DataFrame(js["hourly"])
        f["time"] = pd.to_datetime(f["time"])
        frames.append(f.set_index("time"))
    df = frames[0].join(frames[1], how="outer").sort_index()
    offset = aq.get("utc_offset_seconds", 0)
    now = pd.Timestamp((datetime.now(timezone.utc) + timedelta(seconds=offset))
                       .replace(tzinfo=None)).floor("60min")
    return df, now


def _add_exog(df: pd.DataFrame) -> None:
    h = df.index.hour
    df["hour_sin"] = np.sin(2 * np.pi * h / 24)
    df["hour_cos"] = np.cos(2 * np.pi * h / 24)
    df["dow"] = df.index.dayofweek
    df["temp"] = df["temperature_2m"]
    df["humidity"] = df["relative_humidity_2m"]
    df["wind_speed"] = df["wind_speed_10m"]
    rad = np.deg2rad(df["wind_direction_10m"])
    df["wind_dir_sin"], df["wind_dir_cos"] = np.sin(rad), np.cos(rad)
    df["precip"] = df["precipitation"]


# ---------------------------------------------------------------- model
def _make_model():
    return lgb.LGBMRegressor(
        n_estimators=150, learning_rate=0.05, num_leaves=15, min_child_samples=50,
        subsample=0.8, subsample_freq=1, colsample_bytree=0.8, reg_lambda=5.0,
        importance_type="gain", random_state=42, n_jobs=1, verbose=-1)


def _feature_matrix(ly: pd.Series, exog: pd.DataFrame) -> pd.DataFrame:
    X = pd.DataFrame(index=ly.index)
    s, s25 = ly.shift(1), ly.shift(25)
    X["lvl_24"] = ly.shift(24)
    X["lvl_1"] = s
    X["d1"] = s - s25
    X["d3"] = s.rolling(3).mean() - s25.rolling(3).mean()
    X["d6"] = s.rolling(6).mean() - s25.rolling(6).mean()
    X["d24"] = s.rolling(24).mean() - s25.rolling(24).mean()
    X["slope_3"] = s - ly.shift(3)
    X["std_24"] = s.rolling(24).std()
    for c in EXOG:
        X[c] = exog[c]
    return X[FEATURES]


def _recursive(model, ly_hist: np.ndarray, exog: np.ndarray, steps: int) -> np.ndarray:
    """Forecast = value 24h earlier + predicted change. Predictions feed later steps."""
    buf = list(ly_hist[-48:])
    out = []
    for i in range(steps):
        a = np.array(buf[-48:])
        f = [a[-24], a[-1], a[-1] - a[-25],
             a[-3:].mean() - a[-27:-24].mean(),
             a[-6:].mean() - a[-30:-24].mean(),
             a[-24:].mean() - a[-48:-24].mean(),
             a[-1] - a[-3], a[-24:].std(ddof=1)] + list(exog[i])
        p = a[-24] + float(model.predict(np.array([f]))[0])
        buf.append(p)
        out.append(p)
    return np.array(out)


def _group(f: str) -> str:
    if f.startswith("lvl_"):
        return "Recent PM2.5 levels"
    if f in ("d1", "d3", "d6", "d24", "slope_3", "std_24"):
        return "Trend vs yesterday"
    if f in ("hour_sin", "hour_cos"):
        return "Time of day"
    return {"dow": "Day of week", "temp": "Temperature", "humidity": "Humidity",
            "precip": "Rainfall"}.get(f, "Wind")


def _summ(Em, Eb, sl):
    return {"model_mae": float(np.abs(Em[:, sl]).mean()),
            "base_mae": float(np.abs(Eb[:, sl]).mean()),
            "model_rmse": float(np.sqrt((Em[:, sl] ** 2).mean())),
            "base_rmse": float(np.sqrt((Eb[:, sl] ** 2).mean()))}


def run_forecast(lat: float, lon: float) -> dict:
    try:
        return _run(round(lat, 2), round(lon, 2))
    except Exception as e:  # never crash the UI
        return {"ok": False, "error": f"Forecast failed: {e}"}


@st.cache_resource(ttl=3600, show_spinner=False)
def _run(lat: float, lon: float) -> dict:
    raw = fetch_inputs(lat, lon)
    if raw is None:
        return {"ok": False, "error": "Could not download forecast inputs for this location."}
    df, now = raw
    df = df.reindex(pd.date_range(df.index.min(), df.index.max(), freq=HOUR))
    cams = df["pm2_5"].copy()                      # raw CAMS values incl. future hours
    past = df.index <= now
    if past.sum() < MIN_HOURS or cams[past].notna().mean() < 0.8:
        return {"ok": False, "error": "Not enough valid history (need 30+ days) to train a model here."}

    df[WX_VARS] = df[WX_VARS].interpolate(limit_direction="both")
    _add_exog(df)
    hist = df[past].copy()
    hist["pm2_5"] = hist["pm2_5"].interpolate(method="time", limit_direction="both")

    times = pd.date_range(hist.index[-1] + HOUR, periods=H, freq=HOUR)
    if times[-1] > df.index[-1]:
        return {"ok": False, "error": "Weather forecast does not cover the next 48 hours."}

    y = hist["pm2_5"].clip(lower=0).values
    ly = pd.Series(np.log1p(y), index=hist.index)
    ex = hist[EXOG].values
    X = _feature_matrix(ly, hist)
    tgt = ly - ly.shift(24)
    valid = (X.notna().all(axis=1) & tgt.notna()).values
    n = len(hist)
    split = int(n * 0.8)                           # chronological 80/20

    # --- train on the first 80% only, evaluate on the last 20%
    tr = valid & (np.arange(n) < split)
    model = _make_model().fit(X.values[tr], tgt.values[tr])

    P, A, B = [], [], []
    for o in range(split, n - H, 12):              # forecast origins in the test period
        p = np.expm1(_recursive(model, ly.values[:o + 1], ex[o + 1:o + 1 + H], H))
        P.append(np.clip(p, 0, None))
        A.append(y[o + 1:o + 1 + H])
        # baseline: same hour of the most recent fully observed day
        B.append([y[o + h - 24 * int(np.ceil(h / 24))] for h in range(1, H + 1)])
    if len(P) < 3:
        return {"ok": False, "error": "Not enough test data to evaluate the model."}
    P, A, B = np.array(P), np.array(A), np.array(B)
    Em, Eb = A - P, A - B

    # uncertainty: RMSE per horizon, smoothed, forced to widen with horizon
    sig = pd.Series(np.sqrt((Em ** 2).mean(axis=0))).rolling(5, center=True, min_periods=1).mean()
    sig = sig.cummax().values

    # --- refit on ALL history for the live forecast
    final = _make_model().fit(X.values[valid], tgt.values[valid])
    fex = df.reindex(times)[EXOG].ffill().bfill().values
    pred = np.clip(np.expm1(_recursive(final, ly.values, fex, H)), 0, None)

    imp = pd.Series(final.feature_importances_, index=FEATURES).groupby(_group).sum()
    imp = (imp / imp.sum() * 100).sort_values()

    return {
        "ok": True, "now": now, "times": times, "pred": pred,
        "lo": np.clip(pred - 1.28 * sig, 0, None), "hi": pred + 1.28 * sig,
        "cams": cams.reindex(times).values,
        "history": hist["pm2_5"].iloc[-72:],
        "metrics": {"d1": _summ(Em, Eb, slice(0, 24)), "d2": _summ(Em, Eb, slice(24, 48))},
        "mae_h_model": np.abs(Em).mean(axis=0), "mae_h_base": np.abs(Eb).mean(axis=0),
        "importance": imp, "n_origins": len(P), "test_days": (n - split) / 24,
    }


# ---------------------------------------------------------------- outputs
def best_outdoor_window(res: dict):
    """Best 2-hour window tomorrow between 06:00 and 21:00 (lowest predicted PM2.5)."""
    s = pd.Series(res["pred"], index=res["times"])
    tomorrow = (res["now"] + pd.Timedelta(days=1)).date()
    day = s[(s.index.date == tomorrow) & (s.index.hour >= 6) & (s.index.hour <= 21)]
    if len(day) < 4:
        return None
    two = day.rolling(2).mean().dropna()
    end = two.idxmin()
    return {"start": end - HOUR, "end": end + HOUR, "mean": float(two.min()),
            "day_mean": float(day.mean())}


def forecast_chart(res: dict) -> go.Figure:
    t = res["times"]
    fig = go.Figure()
    h = res["history"]
    fig.add_trace(go.Scatter(x=h.index, y=h.values, name="Recent PM2.5",
                             line=dict(color="#555")))
    fig.add_trace(go.Scatter(x=t, y=res["hi"], line=dict(width=0),
                             showlegend=False, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=t, y=res["lo"], fill="tonexty", line=dict(width=0),
                             fillcolor="rgba(31,119,180,0.2)", name="~80% interval"))
    fig.add_trace(go.Scatter(x=t, y=res["pred"], name="LightGBM forecast",
                             line=dict(color="#1f77b4", width=3)))
    fig.add_trace(go.Scatter(x=t, y=res["cams"], name="CAMS forecast (reference)",
                             line=dict(color="#d62728", dash="dash")))
    fig.add_hline(y=15, line_dash="dot", line_color="orange",
                  annotation_text="WHO 24h guideline")
    fig.update_layout(height=400, yaxis_title="PM2.5 (µg/m³)",
                      margin=dict(l=10, r=10, t=30, b=10),
                      legend=dict(orientation="h", y=1.12))
    return fig


def error_chart(res: dict) -> go.Figure:
    x = np.arange(1, H + 1)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x, y=res["mae_h_model"], name="LightGBM", line=dict(width=3)))
    fig.add_trace(go.Scatter(x=x, y=res["mae_h_base"], name="Baseline (same hour yesterday)",
                             line=dict(dash="dash")))
    fig.update_layout(height=300, xaxis_title="Hours ahead", yaxis_title="MAE (µg/m³)",
                      margin=dict(l=10, r=10, t=30, b=10), legend=dict(orientation="h", y=1.15))
    return fig


def importance_chart(res: dict) -> go.Figure:
    imp = res["importance"]
    fig = go.Figure(go.Bar(x=imp.values, y=imp.index, orientation="h"))
    fig.update_layout(height=300, xaxis_title="Share of model importance (%)",
                      margin=dict(l=10, r=10, t=30, b=10))
    return fig