# tests/test_forecast.py
import json
from datetime import date
from pathlib import Path
import httpx
import pytest

from weather_agent import forecast, recording
from weather_agent.geocode import Candidate

FIX = Path(__file__).parent / "fixtures"
PARIS = Candidate("Paris", "Île-de-France", "France", "FR", 48.8566, 2.3522, "Europe/Paris", 2138551, "PPLC")
def raw(name): return json.loads((FIX / name).read_text())

def test_precheck_rejects_1950():
    with pytest.raises(forecast.DateOutOfRange):
        forecast.precheck(forecast.When("date", date="1950-01"), date(2026, 9, 16))

def test_precheck_accepts_a_date_in_the_window():
    forecast.precheck(forecast.When("date", date="2026-09-20"), date(2026, 9, 16))

def test_precheck_rejects_far_future():
    with pytest.raises(forecast.DateOutOfRange):
        forecast.precheck(forecast.When("date", date="2027-01-01"), date(2026, 9, 16))

def test_request_for_now_asks_current_block():
    params = forecast.build_request(PARIS, forecast.When("now"))["params"]
    assert "temperature_2m" in params["current"] and params["forecast_days"] == 1 and params["timezone"] == "Europe/Paris"

def test_request_for_tomorrow_asks_16_daily_days_without_hourly():
    params = forecast.build_request(PARIS, forecast.When("tomorrow"))["params"]
    assert params["forecast_days"] == 16 and "hourly" not in params and "current" not in params

def test_request_with_part_of_day_adds_hourly():
    params = forecast.build_request(PARIS, forecast.When("today", part_of_day="afternoon"))["params"]
    assert "precipitation_probability" in params["hourly"]

def test_resolve_tomorrow_is_second_local_date():
    r = raw("forecast_paris_daily.json")
    assert forecast.resolve(forecast.When("tomorrow"), r)["dates"] == [r["daily"]["time"][1]]

def test_resolve_weekday_picks_first_matching_day_today_included():
    r = raw("forecast_paris_daily.json")
    first = date.fromisoformat(r["daily"]["time"][0])
    name = first.strftime("%A").lower()
    assert forecast.resolve(forecast.When("weekday", weekday=name), r)["dates"] == [r["daily"]["time"][0]]

def test_resolve_period_returns_seven_dates():
    r = raw("forecast_paris_daily.json")
    assert len(forecast.resolve(forecast.When("period", days=7), r)["dates"]) == 7

def test_resolve_absent_date_raises():
    with pytest.raises(forecast.DateOutOfRange):
        forecast.resolve(forecast.When("date", date="1950-01-01"), raw("forecast_paris_daily.json"))

def test_resolve_afternoon_hours():
    r = raw("forecast_london_hourly.json")
    res = forecast.resolve(forecast.When("today", part_of_day="afternoon"), r)
    assert res["hours"] == [12, 13, 14, 15, 16, 17, 18]

def test_facts_for_now_have_current_and_weather_text():
    f = forecast.facts(PARIS, forecast.When("now"), raw("forecast_paris_now.json"))
    assert "temperature_2m" in f["current"] and isinstance(f["current"]["weather"], str)
    assert f["units"]["temperature"] == "°C" and f["place"]["timezone"] == "Europe/Paris"

def test_facts_daily_rows_carry_weekday_and_verdicts():
    f = forecast.facts(PARIS, forecast.When("tomorrow"), raw("forecast_paris_daily.json"))
    row = f["daily"][0]
    assert set(row) >= {"date", "weekday", "temperature_2m_max", "temperature_2m_min", "precipitation_probability_max"}
    assert f["verdicts"]["rain"] in {"yes", "unlikely", "no"}

def test_rain_verdict_thresholds():
    assert forecast.rain_verdict(50) == "yes" and forecast.rain_verdict(49) == "unlikely" and forecast.rain_verdict(19) == "no"


# Added beyond the plan: behaviour seen in the saved fixtures that the plan's tests do not pin down.

LONDON = Candidate("London", "England", "United Kingdom", "GB", 51.5074, -0.1278, "Europe/London", 8961989, "PPLC")

def test_null_probability_gives_unknown_rain_verdict():
    # Open-Meteo sends null for the last day or two; the fixture has it on day 16.
    f = forecast.facts(PARIS, forecast.When("in_days", days=15), raw("forecast_paris_daily.json"))
    assert f["daily"][0]["precipitation_probability_max"] is None
    assert f["verdicts"]["rain"] == "unknown" and f["verdicts"]["rain_probability_max"] is None

def test_period_skips_null_values_when_taking_the_max():
    f = forecast.facts(PARIS, forecast.When("period", days=15), raw("forecast_paris_daily.json"))
    assert isinstance(f["verdicts"]["rain_probability_max"], int)

def test_evening_stops_at_23_because_there_is_no_24_00_row():
    r = raw("forecast_london_hourly.json")
    f = forecast.facts(LONDON, forecast.When("tomorrow", part_of_day="evening"), r)
    assert f["when"]["hours"] == [18, 19, 20, 21, 22, 23]
    assert [row["time"][-5:] for row in f["hourly"]] == ["18:00", "19:00", "20:00", "21:00", "22:00", "23:00"]
    assert all(row["time"].startswith(r["daily"]["time"][1]) for row in f["hourly"])

def test_month_containing_today_resolves_to_its_forecast_days():
    r = raw("forecast_paris_daily.json")
    month = r["daily"]["time"][0][:7]
    dates = forecast.resolve(forecast.When("date", date=month), r)["dates"]
    assert dates[0] == r["daily"]["time"][0] and all(d.startswith(month) for d in dates)

def test_month_not_containing_today_is_out_of_range():
    r = raw("forecast_paris_daily.json")
    next_month = r["daily"]["time"][-1][:7]
    assert next_month != r["daily"]["time"][0][:7]  # the fixture spans a month boundary
    with pytest.raises(forecast.DateOutOfRange) as caught:
        forecast.resolve(forecast.When("date", date=next_month), r)
    assert caught.value.date == next_month

def test_precheck_window_edges():
    today = date(2026, 9, 16)
    forecast.precheck(forecast.When("date", date="2026-09-15"), today)  # yesterday: local date may lag
    forecast.precheck(forecast.When("date", date="2026-10-01"), today)  # today + 15
    for text in ("2026-09-14", "2026-10-02"):
        with pytest.raises(forecast.DateOutOfRange):
            forecast.precheck(forecast.When("date", date=text), today)
    for days in (0, 16):
        with pytest.raises(ValueError):
            forecast.precheck(forecast.When("in_days", days=days), today)

def test_facts_leave_the_raw_response_untouched():
    r = raw("forecast_paris_now.json")
    before = json.dumps(r, sort_keys=True)
    forecast.facts(PARIS, forecast.When("now"), r)
    assert json.dumps(r, sort_keys=True) == before

def test_now_verdict_is_a_reading_not_a_probability():
    f = forecast.facts(PARIS, forecast.When("now"), raw("forecast_paris_now.json"))
    expected = "yes" if f["current"]["precipitation"] > 0 else "no"
    assert f["verdicts"]["rain"] == expected and isinstance(f["verdicts"]["windy"], bool)

def test_fetch_records_then_replays_offline(tmp_path, monkeypatch):
    monkeypatch.setattr(recording, "FIXTURES", tmp_path)
    body = raw("forecast_paris_now.json")
    client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=body)))
    live, source = forecast.fetch(PARIS, forecast.When("now"), offline=False, client=client)
    assert source == "live" and live["current"]["temperature_2m"] == body["current"]["temperature_2m"]
    replayed, source = forecast.fetch(PARIS, forecast.When("now"), offline=True, client=client)
    assert source == "replayed" and replayed == live

def test_fetch_raises_on_a_400_from_open_meteo(tmp_path, monkeypatch):
    monkeypatch.setattr(recording, "FIXTURES", tmp_path)
    client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(400, json={"error": True})))
    with pytest.raises(httpx.HTTPStatusError):
        forecast.fetch(PARIS, forecast.When("now"), offline=False, client=client)


def test_verdicts_follow_the_asked_aspects():
    r = raw("forecast_paris_daily.json")
    only_rain = forecast.facts(PARIS, forecast.When("tomorrow", aspects=["precipitation"]), r)["verdicts"]
    assert set(only_rain) == {"rain", "rain_probability_max"}
    none = forecast.facts(PARIS, forecast.When("tomorrow", aspects=["temperature"]), r)["verdicts"]
    assert none == {}


def test_precheck_rejects_month_outside_yesterday_to_tomorrow():
    with pytest.raises(forecast.DateOutOfRange):
        forecast.precheck(forecast.When("date", date="2026-10"), date(2026, 9, 16))
    forecast.precheck(forecast.When("date", date="2026-09"), date(2026, 9, 16))


def test_precheck_raises_value_error_for_missing_fields():
    with pytest.raises(ValueError):
        forecast.precheck(forecast.When("date"), date(2026, 9, 16))
    with pytest.raises(ValueError):
        forecast.precheck(forecast.When("period"), date(2026, 9, 16))


def test_weekday_names_are_english_and_fixed():
    assert forecast.weekday_name("2026-09-19") == "Saturday"
