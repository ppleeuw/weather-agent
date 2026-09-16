"""Step 1: the model reads the question and chooses tool calls.

The model sees two tools. lookup_place carries the place name as the user
wrote it; get_forecast carries when and which aspects. Neither tool has a
coordinate or a resolved date: code fills those in later. The model output is
validated here, field by field, and every correction is noted for the trace.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import httpx

from weather_agent import providers
from weather_agent.forecast import When
from weather_agent.providers import CallBudget, ModelResponse, ToolCall

SYSTEM_PROMPT = (
    "You are the understanding step of a weather app. You never answer the question yourself.\n"
    "For a weather question, always call both tools: lookup_place with the place exactly as the "
    "user wrote it, and get_forecast with when and aspects. 'What's the weather' also needs both.\n"
    "A specific date, month or year, past or future, is when=date with the date copied as written, "
    "for example '1950-01'.\n"
    "Copy weekday names and dates as the user wrote them. Never compute or convert a date. "
    "Never estimate coordinates.\n"
    "If the message is not a question about the weather at a place, call no tool and reply "
    "with the single word NONE."
)

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
WHEN_KINDS = ["now", "today", "tomorrow", "weekday", "date", "in_days", "period"]
PARTS_OF_DAY = ["morning", "afternoon", "evening", "night"]
ASPECTS = ["temperature", "precipitation", "wind", "snow", "general"]

LOOKUP_PLACE = {
    "name": "lookup_place",
    "description": (
        "Identify the place the user asks about. Copy the place name as the user wrote it, "
        "without weather words. Fill region and country only if the user named them."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Place name as written, e.g. 'Paris' or 'New York'"},
            "region": {"type": "string", "description": "State, province or region if named, e.g. 'Texas'"},
            "country": {"type": "string", "description": "Country if named, e.g. 'France' or 'US'"},
        },
        "required": ["name"],
    },
}

GET_FORECAST = {
    "name": "get_forecast",
    "description": (
        "Ask for the weather at the place from lookup_place. Describe when and which aspects. "
        "Pass weekday names and dates exactly as the user wrote them; never compute a date."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "when": {"type": "string", "enum": WHEN_KINDS},
            "weekday": {"type": "string", "enum": WEEKDAYS, "description": "Only with when=weekday"},
            "date": {
                "type": "string",
                "description": "Only with when=date. The date the user wrote, ISO style with the precision given: YYYY, YYYY-MM or YYYY-MM-DD",
            },
            "days": {
                "type": "integer",
                "description": "With when=in_days: days from today. With when=period: number of days starting today, e.g. 7 for 'this week'",
            },
            "part_of_day": {"type": "string", "enum": PARTS_OF_DAY},
            "aspects": {"type": "array", "items": {"type": "string", "enum": ASPECTS}},
        },
        "required": ["when", "aspects"],
    },
}

TOOLS = [LOOKUP_PLACE, GET_FORECAST]
TOOL_NAMES = {tool["name"] for tool in TOOLS}


@dataclass
class Place:
    """The place as the user named it, before geocoding."""

    name: str
    region: str | None = None
    country: str | None = None


@dataclass
class Understanding:
    """What code made of the model's tool calls."""

    place: Place | None
    when: When | None
    notes: list[str] = field(default_factory=list)
    unknown_tools: list[str] = field(default_factory=list)
    raw_calls: list[ToolCall] = field(default_factory=list)

    @property
    def asked_weather(self) -> bool:
        """The model called a registered tool, so it read the message as a weather question."""
        return any(call.name in TOOL_NAMES for call in self.raw_calls)


def understand(
    question: str, model_id: str, budget: CallBudget, offline: bool, client: httpx.Client, env: dict
) -> tuple[ModelResponse, Understanding, str]:
    """One model call, then interpretation. Returns (response, understanding, source)."""
    response, source = providers.call_model(model_id, SYSTEM_PROMPT, question, TOOLS, budget, offline, client, env)
    return response, interpret(response.tool_calls), source


def interpret(calls: list[ToolCall]) -> Understanding:
    """Turn tool calls into a validated place and When, noting every correction."""
    notes: list[str] = []
    unknown: list[str] = []
    place: Place | None = None
    forecast_args: dict | None = None
    for call in calls:
        if call.name == "lookup_place":
            if place is not None:
                notes.append(f"lookup_place was called again; {place.name!r} replaced by {call.arguments.get('name')!r}")
            place = _place(call.arguments, notes)
        elif call.name == "get_forecast":
            if forecast_args is not None:
                notes.append("get_forecast was called again; the last call is used")
            forecast_args = call.arguments
        else:
            unknown.append(call.name)
    when: When | None = None
    if place is not None:
        if forecast_args is None:
            forecast_args = {"when": "now", "aspects": ["general"]}
            notes.append("get_forecast was not called; defaulted to now and general")
        when = _when(forecast_args, notes)
    return Understanding(place, when, notes, unknown, list(calls))


def _place(args: dict, notes: list[str]) -> Place | None:
    name = str(args.get("name") or "").strip()
    if not name:
        notes.append("lookup_place had no name")
        return None
    return Place(name, _text_or_none(args.get("region")), _text_or_none(args.get("country")))


def _when(args: dict, notes: list[str]) -> When:
    """Validate types and enums. Whether a date or a day count is in reach is forecast.precheck's job."""
    kind = _choice(args.get("when"), WHEN_KINDS, "when", notes) or "now"
    weekday = _choice(_lower(args.get("weekday")), WEEKDAYS, "weekday", notes)
    part_of_day = _choice(_lower(args.get("part_of_day")), PARTS_OF_DAY, "part_of_day", notes)
    date_text = _text_or_none(args.get("date"))  # kept as written; precheck rejects what it cannot read
    days = args.get("days")
    # bool is a subclass of int: a model that sends true must not pass as days=1.
    if days is not None and (isinstance(days, bool) or not isinstance(days, int) or days < 1):
        notes.append(f"days {days!r} is not a positive whole number; dropped")
        days = None
    raw_aspects = args.get("aspects") or []
    aspects = [a for a in raw_aspects if a in ASPECTS]
    dropped = [a for a in raw_aspects if a not in ASPECTS]
    if dropped:
        notes.append(f"aspects {dropped!r} are not in {ASPECTS}; dropped")
    kind = _repair_kind(kind, weekday, date_text, days, notes)
    if kind == "period" and days is None:
        days = 7
    if kind == "now" and part_of_day:
        notes.append(f"when=now with part_of_day {part_of_day!r}; a part of day is a window, using today")
        kind = "today"
    return When(kind=kind, weekday=weekday, date=date_text, days=days, part_of_day=part_of_day, aspects=aspects or ["general"])


def _repair_kind(kind: str, weekday: str | None, date_text: str | None, days: int | None, notes: list[str]) -> str:
    """A kind without its required field falls back to the nearest sensible kind."""
    if kind == "weekday" and weekday is None:
        notes.append("when=weekday without a weekday; using today")
        return "today"
    if kind == "date" and date_text is None:
        notes.append("when=date without a date; using today")
        return "today"
    if kind == "in_days" and days is None:
        notes.append("when=in_days without days; using tomorrow")
        return "tomorrow"
    if kind == "period" and days is None:
        notes.append("when=period without days; using 7")
    return kind


def _choice(value: str | None, allowed: list[str], field_name: str, notes: list[str]) -> str | None:
    if value is None:
        return None
    if value in allowed:
        return value
    notes.append(f"{field_name} {value!r} is not one of {allowed}; dropped")
    return None


def _text_or_none(value: object) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None


def _lower(value: object) -> str | None:
    return str(value).strip().lower() if value is not None else None
