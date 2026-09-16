"""Verdicts and weather words: the judgement calls, made by code.

Why: the model must never judge a number. Whether 35 percent means rain,
whether 22 km/h is windy, whether a day counts as snow: fixed rules here, so
the answer step only phrases. Only the verdicts for the aspects the user asked
about are returned, so a question about the temperature never gets a rain
verdict to start its sentence with.
"""
from __future__ import annotations

# Thresholds from the design spec: probability in percent, wind in km/h.
RAIN_YES = 50
RAIN_UNLIKELY = 20
WINDY_KMH = 20

# WMO weather interpretation codes, from https://open-meteo.com/en/docs.
WMO_CODES: dict[int, str] = {
    0: "clear sky", 1: "mainly clear", 2: "partly cloudy", 3: "overcast", 45: "fog",
    48: "depositing rime fog", 51: "light drizzle", 53: "moderate drizzle", 55: "dense drizzle",
    56: "light freezing drizzle", 57: "dense freezing drizzle", 61: "slight rain", 63: "moderate rain",
    65: "heavy rain", 66: "light freezing rain", 67: "heavy freezing rain", 71: "slight snowfall",
    73: "moderate snowfall", 75: "heavy snowfall", 77: "snow grains", 80: "slight rain showers",
    81: "moderate rain showers", 82: "violent rain showers", 85: "slight snow showers",
    86: "heavy snow showers", 95: "thunderstorm", 96: "thunderstorm with slight hail",
    99: "thunderstorm with heavy hail",
}
SNOW_CODES = {71, 73, 75, 77, 85, 86}

# Which verdict keys belong to which asked aspect. Temperature and general have none.
ASPECT_VERDICTS = {
    "precipitation": ("rain", "rain_probability_max"),
    "wind": ("windy", "wind_kmh"),
    "snow": ("snow", "snow_days"),
}


def weather_words(code: int | None) -> str:
    return WMO_CODES.get(code, "unknown")  # type: ignore[arg-type]


def verdicts(current: dict | None, daily: list[dict], hourly: list[dict], aspects: list[str]) -> dict:
    """The verdicts for the asked aspects. An empty aspects list keeps every verdict."""
    everything = {**_rain(current, daily, hourly), **_wind(current, daily, hourly), **_snow(current, daily)}
    if not aspects:
        return everything
    wanted = [key for aspect in aspects for key in ASPECT_VERDICTS.get(aspect, ())]
    return {key: everything[key] for key in wanted}


def _rain(current: dict | None, daily: list[dict], hourly: list[dict]) -> dict:
    """With an hour window only that window's rows are judged, and only on the first selected day."""
    rows, key = (hourly, "precipitation_probability") if hourly else (daily, "precipitation_probability_max")
    probability = max_known(rows, key)
    if current is not None:
        # "Now" is a reading, not a forecast: it rains or it does not.
        return {"rain": "yes" if current["precipitation"] > 0 else "no", "rain_probability_max": probability}
    return {"rain": rain_verdict(probability), "rain_probability_max": probability}


def _wind(current: dict | None, daily: list[dict], hourly: list[dict]) -> dict:
    if current is not None:
        wind = current["wind_speed_10m"]
    elif hourly:
        wind = max_known(hourly, "wind_speed_10m")
    else:
        wind = max_known(daily, "wind_speed_10m_max")
    return {"windy": None if wind is None else wind >= WINDY_KMH, "wind_kmh": wind}


def _snow(current: dict | None, daily: list[dict]) -> dict:
    # `or 0` treats a null (no data) like 0.0: neither counts as snow.
    snow_days = [row["weekday"] for row in daily if (row.get("snowfall_sum") or 0) > 0]
    snowing_now = current is not None and current.get("weather_code") in SNOW_CODES
    return {"snow": snowing_now or len(snow_days) > 0, "snow_days": snow_days}


def max_known(rows: list[dict], key: str) -> float | None:
    """Largest value present; Open-Meteo sends null where the forecast runs out."""
    values = [row[key] for row in rows if row.get(key) is not None]
    return max(values) if values else None


def rain_verdict(probability: float | None) -> str:
    """yes from 50 percent, unlikely from 20, no below; unknown when the API sent no number."""
    if probability is None:
        return "unknown"
    if probability >= RAIN_YES:
        return "yes"
    if probability >= RAIN_UNLIKELY:
        return "unlikely"
    return "no"
