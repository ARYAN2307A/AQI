import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def daily_mean(df: pd.DataFrame, col: str) -> pd.Series:
    return df[col].resample("D").mean().dropna()


def hourly_profile(df: pd.DataFrame, col: str) -> pd.Series:
    return df[col].groupby(df.index.hour).mean()


def weekday_profile(df: pd.DataFrame, col: str) -> pd.Series:
    return df[col].groupby(df.index.dayofweek).mean().reindex(range(7))


def exceedance(df: pd.DataFrame, col: str, limit: float) -> tuple[int, int]:
    """(days whose daily mean exceeds the WHO 24h guideline, total days)."""
    d = daily_mean(df, col)
    return int((d > limit).sum()), len(d)


def trend(df: pd.DataFrame, col: str):
    """Linear trend on daily means. Returns dict or None if < 5 days."""
    d = daily_mean(df, col)
    if len(d) < 5:
        return None
    slope, _ = np.polyfit(np.arange(len(d)), d.values, 1)
    base = d.mean()
    rel = slope * (len(d) - 1) / base if base else 0.0  # total change vs mean
    if rel > 0.10:
        direction = "Rising ↗"
    elif rel < -0.10:
        direction = "Falling ↘"
    else:
        direction = "Stable →"
    return {"slope": slope, "rel": rel, "direction": direction}


def line_chart(df, col, name, limit):
    fig = px.line(df.reset_index(), x="time", y=col,
                  labels={"time": "", col: f"{name} (µg/m³)"})
    fig.add_hline(y=limit, line_dash="dash", line_color="orange",
                  annotation_text="WHO 24h guideline")
    fig.update_layout(height=350, margin=dict(l=10, r=10, t=30, b=10))
    return fig


def daily_bar_chart(df, col, name, limit):
    d = daily_mean(df, col)
    colors = ["#e60000" if v > limit else "#00a000" for v in d.values]
    fig = go.Figure(go.Bar(x=d.index, y=d.values, marker_color=colors))
    fig.add_hline(y=limit, line_dash="dash", line_color="orange",
                  annotation_text="WHO 24h guideline")
    fig.update_layout(height=320, yaxis_title=f"Daily mean {name} (µg/m³)",
                      margin=dict(l=10, r=10, t=30, b=10))
    return fig


def hourly_chart(df, col, name):
    s = hourly_profile(df, col)
    fig = px.line(x=s.index, y=s.values, markers=True,
                  labels={"x": "Hour of day (local)", "y": f"Avg {name} (µg/m³)"})
    fig.update_layout(height=300, margin=dict(l=10, r=10, t=30, b=10))
    return fig


def weekday_chart(df, col, name):
    s = weekday_profile(df, col)
    fig = px.bar(x=WEEKDAYS, y=s.values,
                 labels={"x": "", "y": f"Avg {name} (µg/m³)"})
    fig.update_layout(height=300, margin=dict(l=10, r=10, t=30, b=10))
    return fig

def heatmap_chart(df, col, name):
    """Day x hour heatmap of the selected pollutant."""
    d = df[[col]].copy()
    d["date"] = d.index.strftime("%d %b")
    d["hour"] = d.index.hour
    order = list(dict.fromkeys(d["date"]))          # keep chronological order
    pv = d.pivot_table(index="date", columns="hour", values=col, aggfunc="mean").reindex(order)
    fig = go.Figure(go.Heatmap(
        z=pv.values, x=pv.columns, y=pv.index, colorscale="YlOrRd",
        colorbar=dict(title="µg/m³"), hoverongaps=False,
        hovertemplate="%{y}, %{x}:00<br>" + name + ": %{z:.1f} µg/m³<extra></extra>"))
    fig.update_layout(height=min(700, max(280, 24 * len(pv) + 120)),
                      xaxis_title="Hour of day (local)", yaxis=dict(autorange="reversed"),
                      margin=dict(l=10, r=10, t=30, b=10))
    return fig