"""The four eval layers and the answer rules, all plain code, no model as judge.

Layers: tools (which tools the model called), usage (place, coordinates, date,
requested block), grounding (the guardrail's verdict on the numbers) and rules
(what the answer text must contain). Each returns a LayerResult with a reason,
so a failure says which layer broke and why.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from math import asin, cos, radians, sin, sqrt
from typing import Callable
from zoneinfo import ZoneInfo

from weather_agent import guardrails, pipeline
from weather_agent.eval.golden import GoldenItem
from weather_agent.trace import Step, Trace

RADIUS_KM = 50
EARTH_RADIUS_KM = 6371
LAYERS = ["tools", "usage", "grounding", "rules"]
# Function words that English weather sentences never use; enough to tell the language apart.
DUTCH_WORDS = {"het", "een", "en", "met", "van", "nu", "graden", "momenteel"}


@dataclass
class LayerResult:
    layer: str
    applicable: bool
    passed: bool
    reason: str


def check_item(item: GoldenItem, trace: Trace) -> list[LayerResult]:
    return [check_tools(item, trace), check_usage(item, trace), check_grounding(item, trace), check_rules(item, trace)]


def check_tools(item: GoldenItem, trace: Trace) -> LayerResult:
    if trace.outcome == "upstream_error":
        return LayerResult("tools", True, False, f"upstream error, no tool calls observed: {trace.error_detail[:80]}")
    called = tool_names(trace)
    if called in item.expected_tools:
        return LayerResult("tools", True, True, f"called {called}")
    return LayerResult("tools", True, False, f"called {called}, expected one of {item.expected_tools}")


def check_usage(item: GoldenItem, trace: Trace) -> LayerResult:
    problems: list[str] = []
    if trace.outcome != item.expected_outcome:
        problems.append(f"outcome {trace.outcome}, expected {item.expected_outcome}")
    forecast_step = step_named(trace, "forecast")
    if item.no_forecast_call and forecast_step is not None and forecast_step.source != "skipped":
        problems.append("a forecast call was made")
    place = chosen_place(trace)
    problems += _place_problems(item, place)
    facts = facts_of(trace)
    if facts is not None and forecast_step is not None:
        problems += _when_problems(item, facts, forecast_step.source)
        problems += _block_problems(item, facts)
    return LayerResult("usage", True, not problems, "; ".join(problems) or "outcome, place, date and block as expected")


def check_grounding(item: GoldenItem, trace: Trace) -> LayerResult:
    if trace.outcome != "weather":
        return LayerResult("grounding", False, True, "no weather answer to ground")
    event = next((g for g in trace.guardrails if g.rule == "grounding"), None)
    if event is None:
        return LayerResult("grounding", True, False, "no grounding event in the trace")
    return LayerResult("grounding", True, event.outcome == "pass", event.detail)


def check_rules(item: GoldenItem, trace: Trace) -> LayerResult:
    if not item.rules:
        return LayerResult("rules", False, True, "no rules for this item")
    failures = []
    for name in item.rules:
        ok, reason = RULES[name](trace)
        if not ok:
            failures.append(f"{name}: {reason}")
    return LayerResult("rules", True, not failures, "; ".join(failures) or f"{len(item.rules)} rules passed")


# Helpers that read the trace


def step_named(trace: Trace, name: str) -> Step | None:
    return next((s for s in trace.steps if s.name == name), None)


def tool_names(trace: Trace) -> list[str]:
    step = step_named(trace, "understand")
    if step is None or not step.result:
        return []
    return [call["name"] for call in step.result.get("tool_calls", [])]


def chosen_place(trace: Trace) -> dict | None:
    step = step_named(trace, "geocode")
    return step.result.get("place") if step is not None and step.result else None


def facts_of(trace: Trace) -> dict | None:
    step = step_named(trace, "forecast")
    return step.result.get("facts") if step is not None and step.result else None


def haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Great-circle distance between two latitude/longitude pairs."""
    lat1, lon1, lat2, lon2 = map(radians, (a[0], a[1], b[0], b[1]))
    h = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2) ** 2
    return 2 * EARTH_RADIUS_KM * asin(sqrt(h))


def _place_problems(item: GoldenItem, place: dict | None) -> list[str]:
    problems = []
    if item.country_code and (place is None or place["country_code"] != item.country_code):
        problems.append(f"place {place and place['country_code']}, expected {item.country_code}")
    if item.admin1_contains and (place is None or item.admin1_contains.lower() not in place["admin1"].lower()):
        problems.append(f"region {place and place['admin1']!r} does not contain {item.admin1_contains!r}")
    if item.city_centre and place is not None:
        km = haversine_km(item.city_centre, (place["latitude"], place["longitude"]))
        if km > RADIUS_KM:
            problems.append(f"{km:.0f} km from the expected city centre")
    return problems


def _when_problems(item: GoldenItem, facts: dict, source: str) -> list[str]:
    """The resolved dates must match the question, checked independently with zoneinfo."""
    kind, dates = facts["when"]["kind"], facts["when"]["dates"]
    if item.expected_when and kind not in item.expected_when:
        return [f"when {kind}, expected one of {item.expected_when}"]
    if source == "replayed":
        today = date.fromisoformat(facts["today"])  # a recording keeps its own clock
    else:
        today = datetime.now(ZoneInfo(facts["place"]["timezone"])).date()
        if facts["today"] != today.isoformat():
            return [f"service said today is {facts['today']}, the clock says {today}"]
    resolved = [date.fromisoformat(d) for d in dates]
    if kind in ("now", "today") and resolved != [today]:
        return [f"dates {dates}, expected today"]
    if kind == "tomorrow" and resolved != [today + timedelta(days=1)]:
        return [f"dates {dates}, expected tomorrow {today + timedelta(days=1)}"]
    if kind == "weekday" and item.expected_weekday:
        if len(resolved) != 1 or resolved[0].strftime("%A") != item.expected_weekday or not 0 <= (resolved[0] - today).days <= 6:
            return [f"dates {dates}, expected the next {item.expected_weekday}"]
    if kind == "period" and item.expected_days and (len(resolved) != item.expected_days or resolved[0] != today):
        return [f"{len(resolved)} dates from {dates[:1]}, expected {item.expected_days} from today"]
    return []


def _block_problems(item: GoldenItem, facts: dict) -> list[str]:
    if item.expected_block == "current" and facts.get("current") is None:
        return ["no current block was requested"]
    if item.expected_block == "daily" and (not facts.get("daily") or facts.get("current") is not None):
        return ["expected a daily forecast, not current conditions"]
    if item.expected_block == "hourly" and not facts.get("hourly"):
        return ["no hourly rows for the part of day"]
    return []


# Answer rules: each takes the trace and returns (ok, reason)


def _first_word(text: str) -> str:
    return re.sub(r"[^a-z]", "", text.strip().split(" ")[0].lower()) if text.strip() else ""


def has_celsius(t: Trace) -> tuple[bool, str]:
    return "°C" in t.answer, "no °C in the answer"


def has_kmh(t: Trace) -> tuple[bool, str]:
    return "km/h" in t.answer.lower(), "no km/h in the answer"


def has_percent(t: Trace) -> tuple[bool, str]:
    return "%" in t.answer or "percent" in t.answer.lower(), "no percentage in the answer"


def starts_yes_no_unlikely(t: Trace) -> tuple[bool, str]:
    return _first_word(t.answer) in {"yes", "no", "unlikely"}, f"starts with {t.answer[:20]!r}"


def starts_yes_no(t: Trace) -> tuple[bool, str]:
    return _first_word(t.answer) in {"yes", "no"}, f"starts with {t.answer[:20]!r}"


def mentions_texas(t: Trace) -> tuple[bool, str]:
    return "texas" in t.answer.lower(), "Texas is not mentioned"


def two_celsius_values(t: Trace) -> tuple[bool, str]:
    count = len(re.findall(r"-?\d+(?:[.,]\d+)?\s*°C", t.answer))
    return count >= 2, f"{count} temperature values, expected two"


def names_the_date(t: Trace) -> tuple[bool, str]:
    facts = facts_of(t)
    if not facts or not facts["when"]["dates"]:
        return False, "no resolved date"
    day = date.fromisoformat(facts["when"]["dates"][0])
    # (?<!\d) and (?!\d) accept "16th" and "16 September" but not "2016" or "160".
    named = day.strftime("%A").lower() in t.answer.lower() or re.search(rf"(?<!\d){day.day}(?!\d)", t.answer) is not None
    return named, f"neither {day.strftime('%A')} nor {day.day} appears"


def names_days_if_snow(t: Trace) -> tuple[bool, str]:
    facts = facts_of(t)
    verdicts = facts.get("verdicts", {}) if facts else {}
    if not verdicts.get("snow"):
        return True, "no snow expected"
    missing = [d for d in verdicts.get("snow_days", []) if d.lower() not in t.answer.lower()]
    return not missing, f"snow days not named: {missing}"


def is_dutch(t: Trace) -> tuple[bool, str]:
    words = set(re.findall(r"[a-zà-ü]+", t.answer.lower()))
    return bool(words & DUTCH_WORDS), "no Dutch words found"


def no_system_prompt(t: Trace) -> tuple[bool, str]:
    return guardrails.check_leak(t.answer, pipeline.SYSTEM_PROMPTS)


def max_three_sentences(t: Trace) -> tuple[bool, str]:
    count = len(re.findall(r"[.!?](?:\s|$)", t.answer))
    return count <= 3, f"{count} sentences"


def three_suggestions(t: Trace) -> tuple[bool, str]:
    ok = len(t.suggestions) == 3 and all("," in s for s in t.suggestions)
    return ok, f"{len(t.suggestions)} suggestions: {t.suggestions}"


def _contains(fragment: str) -> Callable[[Trace], tuple[bool, str]]:
    def rule(t: Trace) -> tuple[bool, str]:
        return fragment in t.answer, f"answer lacks {fragment!r}"

    return rule


RULES: dict[str, Callable[[Trace], tuple[bool, str]]] = {
    "has_celsius": has_celsius,
    "has_kmh": has_kmh,
    "has_percent": has_percent,
    "starts_yes_no_unlikely": starts_yes_no_unlikely,
    "starts_yes_no": starts_yes_no,
    "mentions_texas": mentions_texas,
    "two_celsius_values": two_celsius_values,
    "names_the_date": names_the_date,
    "names_days_if_snow": names_days_if_snow,
    "is_dutch": is_dutch,
    "no_system_prompt": no_system_prompt,
    "max_three_sentences": max_three_sentences,
    "three_suggestions": three_suggestions,
    "template_out_of_range": _contains("current conditions"),
    "template_not_found": _contains("could not find"),
    "template_which": _contains("Which"),
    "template_only_weather": _contains("only help with the weather"),
    "template_too_long": _contains("500 characters"),
}
