"""Open-Meteo forecast: request shapes, date resolution and the facts object.

Why: the model must never compute a date. It reports the user's wording
("tomorrow", "saturday", "2026-09-20", "afternoon") in a `When`; this module
turns that into the exact API call, picks the matching local dates from the
response, and builds the facts object that the answer step and the grounding
check read. The judgement calls live in verdicts.py. The understand step has
already validated the values in `When`.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta

import httpx

from weather_agent import recording
from weather_agent.geocode import Candidate
from weather_agent.verdicts import verdicts, weather_words

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
TIMEOUT_S = 10  # Open-Meteo answers in well under a second; ten seconds covers a slow link
FORECAST_DAYS = 16  # the most Open-Meteo serves
MAX_DAYS = 15  # the last day index the user can ask for
DATE_RE = re.compile(r"^\d{4}(-\d{2}(-\d{2})?)?$")  # YYYY, YYYY-MM or YYYY-MM-DD

# Variable names from https://open-meteo.com/en/docs. A "now" question also gets
# today's range (NOW_DAILY_VARS) so the answer can give context.
CURRENT_VARS = ["temperature_2m", "apparent_temperature", "relative_humidity_2m", "precipitation",
                "weather_code", "wind_speed_10m", "wind_gusts_10m", "is_day"]
DAILY_VARS = ["temperature_2m_max", "temperature_2m_min", "precipitation_probability_max",
              "precipitation_sum", "snowfall_sum", "weather_code", "wind_speed_10m_max"]
NOW_DAILY_VARS = ["temperature_2m_max", "temperature_2m_min", "precipitation_probability_max",
                  "precipitation_sum", "weather_code"]
HOURLY_VARS = ["temperature_2m", "precipitation_probability", "precipitation", "weather_code",
               "wind_speed_10m"]
# Open-Meteo defaults; the request never asks for other units.
UNITS = {"temperature": "°C", "wind_speed": "km/h", "precipitation": "mm", "snowfall": "cm",
         "probability": "%"}

# Hour windows, both ends inclusive. Hour 24 has no row and is dropped in resolve().
PART_OF_DAY_HOURS = {"morning": (6, 12), "afternoon": (12, 18), "evening": (18, 24), "night": (0, 6)}
# Fixed English names, independent of the server's locale; they match understand's enum.
WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


@dataclass
class When:
    """What the user asked about in time, as the understand step reported it."""

    kind: str  # now, today, tomorrow, weekday, date, in_days, period
    weekday: str | None = None
    date: str | None = None  # YYYY, YYYY-MM or YYYY-MM-DD, as the user wrote it
    days: int | None = None
    part_of_day: str | None = None
    aspects: list[str] = field(default_factory=list)


class DateOutOfRange(Exception):
    """The asked date lies outside the sixteen days Open-Meteo serves."""

    def __init__(self, text: str) -> None:
        super().__init__(f"date out of range: {text}")
        self.date = text


def precheck(when: When, today: date) -> None:
    """Reject, before any network call, what a sixteen-day forecast can never cover.

    The understand step has checked types and enums; this is the one place that
    decides whether the asked time is in reach.
    """
    if when.kind == "date":
        if not _readable_date(when.date):
            raise DateOutOfRange(when.date)  # not a date this app can read, so not one it can serve
        # Local dates differ from the server date by at most a day, so yesterday through
        # today + 16 is the widest window for a full date; resolve() does the exact check
        # on the dates the service returns. A month or a year only passes when it
        # contains today, so its window is yesterday through tomorrow.
        offsets = range(-1, 2) if len(when.date) < 10 else range(-1, FORECAST_DAYS + 1)
        window = [today + timedelta(days=offset) for offset in offsets]
        if not any(day.isoformat().startswith(when.date) for day in window):
            raise DateOutOfRange(when.date)
    if when.kind in ("in_days", "period") and when.days > MAX_DAYS:
        raise DateOutOfRange(label(when))


def _readable_date(text: str) -> bool:
    """True for a real date written as YYYY, YYYY-MM or YYYY-MM-DD."""
    if not DATE_RE.match(text):
        return False
    parts = [int(p) for p in text.split("-")]
    try:
        date(parts[0], parts[1] if len(parts) > 1 else 1, parts[2] if len(parts) > 2 else 1)
    except ValueError:
        return False
    return True


def build_request(place: Candidate, when: When) -> dict:
    """The exact Open-Meteo call for this question; recording.py keys on it too."""
    params: dict = {"latitude": place.latitude, "longitude": place.longitude, "timezone": place.timezone}
    if when.kind == "now":
        params["current"] = ",".join(CURRENT_VARS)
        params["daily"] = ",".join(NOW_DAILY_VARS)
        params["forecast_days"] = 1
    else:
        params["daily"] = ",".join(DAILY_VARS)
        params["forecast_days"] = FORECAST_DAYS
        if when.part_of_day:
            params["hourly"] = ",".join(HOURLY_VARS)
    return {"url": FORECAST_URL, "params": params}


def fetch(place: Candidate, when: When, offline: bool, client: httpx.Client) -> tuple[dict, str]:
    """Return (raw response, source), where source is "live" or "replayed"."""
    request = build_request(place, when)

    def live() -> dict:
        response = client.get(request["url"], params=request["params"], timeout=TIMEOUT_S)
        response.raise_for_status()  # a 400 from Open-Meteo raises here; the pipeline maps it
        return response.json()

    return recording.fetch("forecast", request, live, offline)


def resolve(when: When, raw: dict) -> dict:
    """Pick the local dates (and hours) asked about from the response.

    Open-Meteo returns dates in the place's own timezone, so "today" is today there.
    """
    times: list[str] = raw["daily"]["time"]
    if when.kind == "tomorrow":
        dates = [times[1]]
    elif when.kind == "weekday":
        dates = [_first_weekday(when.weekday, times)]
    elif when.kind == "date":
        dates = _matching_dates(when.date, times)
    elif when.kind == "in_days":
        dates = [times[when.days]]
    elif when.kind == "period":
        dates = times[:when.days]
    else:  # now and today
        dates = [times[0]]
    hours = None
    hourly_day = dates[0]
    if when.part_of_day:
        start, end = PART_OF_DAY_HOURS[when.part_of_day]
        hours = [hour for hour in range(start, end + 1) if hour < 24]
        if when.part_of_day == "night":
            # "Tonight" is the night that starts today, so its small hours belong to the next date.
            hourly_day = _day_after(dates[0], times)
    return {"kind": when.kind, "label": label(when), "dates": dates, "hours": hours, "hourly_day": hourly_day, "days": when.days}


def _day_after(day: str, times: list[str]) -> str | None:
    index = times.index(day) + 1
    return times[index] if index < len(times) else None


def _first_weekday(weekday: str, times: list[str]) -> str:
    """The first forecast day with that name, today included."""
    for day in times:
        if weekday_name(day).lower() == weekday:
            return day
    # Sixteen days always include every weekday, so only a misspelt name gets here.
    raise ValueError(f"unknown weekday {weekday!r}")


def _matching_dates(text: str, times: list[str]) -> list[str]:
    """Days starting with the text: one for a full date, several for a month or year."""
    matching = [day for day in times if day.startswith(text)]
    # A month or year must contain today (spec 4.3); otherwise the forecast does not reach it.
    is_partial = len(text) < 10
    if not matching or (is_partial and times[0] not in matching):
        raise DateOutOfRange(text)
    return matching


def label(when: When) -> str:
    """Short English wording of the asked time, for the trace and the answer model."""
    if when.kind == "weekday":
        text = when.weekday.capitalize()
    elif when.kind == "date":
        text = when.date
    elif when.kind == "in_days":
        text = "in 1 day" if when.days == 1 else f"in {when.days} days"
    elif when.kind == "period":
        text = f"the next {when.days} days"
    else:
        text = when.kind  # now, today and tomorrow read as they are
    return f"{text} {when.part_of_day}" if when.part_of_day else text


def weekday_name(day: str) -> str:
    """'2026-09-17' -> 'Thursday'."""
    return WEEKDAYS[date.fromisoformat(day).weekday()]


def facts(place: Candidate, when: When, raw: dict) -> dict:
    """Everything the answer may say, as plain numbers plus the WMO weather in words."""
    resolved = resolve(when, raw)
    current = None
    if when.kind == "now":
        current = dict(raw["current"])  # a copy: the raw response in the trace stays as received
        current["weather"] = weather_words(current["weather_code"])
    daily = [_daily_row(raw["daily"], day) for day in resolved["dates"]]
    hourly = _hourly_rows(raw, resolved["hourly_day"], resolved["hours"])
    return {
        "place": {"name": place.name, "admin1": place.admin1, "country": place.country,
                  "country_code": place.country_code, "latitude": place.latitude,
                  "longitude": place.longitude, "timezone": place.timezone},
        "today": raw["daily"]["time"][0],
        "when": resolved,
        "current": current,
        "daily": daily,
        "hourly": hourly,
        "units": UNITS,
        "verdicts": verdicts(current, daily, hourly, when.aspects),
    }


def _row_at(block: dict, index: int) -> dict:
    """One time step as a flat dict; Open-Meteo stores each variable as a column."""
    row = {name: values[index] for name, values in block.items()}
    row["weather"] = weather_words(row.get("weather_code"))
    return row


def _daily_row(daily: dict, day: str) -> dict:
    """A daily row keyed by date and weekday, the way the spec's facts object shows it."""
    row = {"date": day, "weekday": weekday_name(day)}
    row.update(_row_at(daily, daily["time"].index(day)))
    del row["time"]  # the same value as "date"
    return row


def _hourly_rows(raw: dict, day: str | None, hours: list[int] | None) -> list[dict]:
    """The rows of one day inside the asked hour window; [] when no part of day was asked."""
    if hours is None or day is None or "hourly" not in raw:
        return []
    times: list[str] = raw["hourly"]["time"]
    wanted = [f"{day}T{hour:02d}:00" for hour in hours]
    return [_row_at(raw["hourly"], times.index(stamp)) for stamp in wanted if stamp in times]
