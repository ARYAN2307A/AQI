# 🌫️ Real-Time Air Quality Monitoring & Prediction

An interactive Streamlit dashboard that lets you pick **any location on a map**, choose a **time window**, and instantly see current air quality, pollution trends, a **48-hour PM2.5 machine-learning forecast**, publicly reported environmental/compliance news, and practical health recommendations.

> 2nd / 3rd Year · Problem 03 — *Real-Time Air Quality Monitoring and Prediction for User-Selected Regions*

<!-- Add a screenshot or GIF here:
![Dashboard preview](docs/screenshot.png)
-->
<img width="959" height="537" alt="image" src="https://github.com/user-attachments/assets/9a9244c7-4e21-4b5b-8393-a73d1372680e" />
---
<img width="959" height="532" alt="image" src="https://github.com/user-attachments/assets/c39b04bf-9be1-459d-ad49-aba9c793cf7c" />
---
<img width="959" height="528" alt="image" src="https://github.com/user-attachments/assets/a10131da-fae3-4319-9b75-219753d0cd1e" />
---
<img width="959" height="532" alt="image" src="https://github.com/user-attachments/assets/6c18c45c-214e-4920-8749-3df8d13b3261" />
---
<img width="959" height="533" alt="image" src="https://github.com/user-attachments/assets/73176b70-dd73-4000-9458-032241c6b891" />
---

## ✨ Features

| Objective | How it's implemented |
|---|---|
| Select a location on a map | Click anywhere on an interactive Folium/OpenStreetMap map, search a city by name, or use quick-pick cities |
| Retrieve real-time / open-source AQ data | [Open-Meteo Air Quality API](https://open-meteo.com/en/docs/air-quality-api) (CAMS model data), with geocoding via Open-Meteo and reverse geocoding via OpenStreetMap Nominatim |
| Specify a time window | Sidebar slider: 24 hours, 3, 7, 14, 30, or 90 days |
| Analyze historical / current trends | Daily means, linear trend detection (rising / falling / stable), hour-of-day and day-of-week profiles, day × hour heatmap, WHO guideline exceedance counts |
| Predict future air quality with a basic ML model | LightGBM recursive 48-hour PM2.5 forecast with an ~80% prediction interval |
| Display PM₂.₅, PM₁₀, NO₂, SO₂, O₃ (and CO) | Live pollutant readings compared against **WHO 2021 24-hour guidelines**, plus overall US AQI category |
| Retrieve environmental / compliance information | Aggregates public news headlines (Google News, Bing News, GDELT) filtered by pollution and compliance keywords |
| Present best practices | Rule-based recommendations driven by AQI band, dominant pollutant, and the forecast, including a suggested best outdoor window for tomorrow |

## 🖥️ App Tabs

1. **📊 Overview** — current AQI, category, and each pollutant vs. its WHO guideline
2. **📈 Trends** — time series, daily bar chart, hourly/weekday patterns, heatmap, and trend direction for the selected pollutant
3. **🔮 Forecast** — 48-hour PM2.5 forecast with uncertainty band, CAMS reference forecast, error-by-horizon vs. baseline, and feature-importance breakdown
4. **📰 Environmental & Compliance** — recent publicly reported pollution/compliance news for the selected region, with fallback search links
5. **💡 Recommendations** — personal, sensitive-group, and community actions based on current conditions

## 🤖 Forecasting Approach

The forecasting module lives in [`forecast.py`](forecast.py).

- **Model:** `LightGBMRegressor`, trained per location on demand
- **Training data:** 90 days of hourly PM2.5 plus weather (temperature, humidity, wind speed/direction, precipitation)
- **Target:** change in log(PM2.5) versus the same hour 24 hours earlier
- **Features:** recent levels and lags, short/long-term deltas vs. yesterday, rolling volatility, cyclical hour-of-day, day-of-week, and weather covariates
- **Inference:** recursive multi-step prediction over a 48-hour horizon, using forecasted weather as inputs
- **Validation:** chronological 80/20 split with rolling forecast origins on the held-out period
- **Baseline:** "same hour of the most recent observed day" — the app reports MAE/RMSE for both the model and the baseline so you can see whether the ML model actually adds value
- **Uncertainty:** per-horizon RMSE from the test period, smoothed and forced to widen with horizon, shown as an ~80% interval

> The model needs at least 30 days of valid history for a location; otherwise the app shows a message instead of a forecast.

## 🗂️ Project Structure

```
air_quality/
├── app.py            # Streamlit UI: sidebar, map, and the five tabs
├── data.py           # Open-Meteo fetching, geocoding, caching, cleaning
├── analysis.py       # Trend statistics, exceedance counts, Plotly charts
├── forecast.py       # LightGBM training, evaluation, 48h recursive forecast
├── news.py           # Multi-source news retrieval + keyword filtering
├── advice.py         # Rule-based health & community recommendations
├── utils.py          # AQI bands/colors and WHO guideline constants
├── requirements.txt
└── .streamlit/
    └── config.toml   # Dark theme configuration
```

## 🚀 Getting Started

### Prerequisites

- Python 3.10+ (developed on 3.13)
- Internet connection (all data comes from public APIs; no API keys required)

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/ARYAN2307A/AQI.git
cd AQI

# 2. Create and activate a virtual environment
python -m venv venv
# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the app
streamlit run app.py
```

The app opens at `http://localhost:8501`.

### Usage

1. Search a city in the sidebar, tap a quick-pick, or **click anywhere on the map**
2. Choose an analysis window and a pollutant for the Trends tab
3. Browse the tabs — the forecast trains automatically for the selected location the first time you open it (cached for an hour afterward)

## 🧰 Tech Stack

- **UI:** [Streamlit](https://streamlit.io/), [Folium](https://python-visualization.github.io/folium/) + [streamlit-folium](https://github.com/randyzwitch/streamlit-folium)
- **Data:** pandas, NumPy, requests
- **Visualization:** Plotly
- **ML:** LightGBM, scikit-learn
- **News parsing:** feedparser

## 🌐 Data Sources

| Source | Used for |
|---|---|
| [Open-Meteo Air Quality API](https://open-meteo.com/en/docs/air-quality-api) | Pollutant concentrations and US AQI (Copernicus CAMS model) |
| [Open-Meteo Forecast API](https://open-meteo.com/en/docs) | Weather features for the ML model |
| [Open-Meteo Geocoding API](https://open-meteo.com/en/docs/geocoding-api) | City search |
| [OpenStreetMap Nominatim](https://nominatim.openstreetmap.org/) | Reverse geocoding of map clicks |
| Google News RSS, Bing News RSS, GDELT | Public environmental / compliance headlines |
| [WHO Global Air Quality Guidelines (2021)](https://www.who.int/publications/i/item/9789240034228) | 24-hour pollutant guideline values |

## ⚠️ Limitations & Disclaimers

- Values are **model-based estimates (CAMS)**, not raw readings from ground monitoring stations, so local accuracy may differ from official sensors.
- The forecast is a **basic, per-request ML model** intended for demonstration; always check the displayed error metrics and baseline comparison.
- News results are **media headlines**, not official regulatory findings or legal determinations.
- Recommendations are **general guidance, not medical advice**. Consult a healthcare professional for personal health concerns.
- Free public APIs may rate-limit; the app retries and falls back across sources where possible.

## 🔮 Future Improvements

- Add ground-station data (e.g., OpenAQ) alongside model estimates
- Multi-pollutant forecasting
- Region/polygon selection and multi-location comparison
- Export reports (CSV / PDF)
- Scheduled model retraining and persisted models

## 🙌 Acknowledgements

Open-Meteo, Copernicus Atmosphere Monitoring Service (CAMS), OpenStreetMap contributors, and the World Health Organization for open data and guidelines.
