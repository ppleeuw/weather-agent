"""The pipeline: one request from question to answer, fully traced.

Order: guardrails before, understand (model), geocode (service), forecast
(service), answer (model), guardrails after. Each step appends to the trace.
Any provider or network failure becomes the outcome upstream_error with a
friendly sentence for the user and the full detail in the trace.
"""
from __future__ import annotations

import time
from dataclasses import asdict
from datetime import datetime, timezone

import httpx

from weather_agent import answer, config, forecast, geocode, guardrails, pricing, recording, trace, understand
from weather_agent.config import Settings
from weather_agent.forecast import When
from weather_agent.geocode import Candidate
from weather_agent.providers import BudgetExceeded, CallBudget, ModelResponse, ProviderError
from weather_agent.trace import Step, Trace

GEOCODE_HANDLER = "open-meteo-geocoding"
FORECAST_HANDLER = "open-meteo-forecast"
SYSTEM_PROMPTS = [understand.SYSTEM_PROMPT, answer.SYSTEM_PROMPT]
STEP_ORDER = ["understand", "geocode", "forecast", "answer"]
SERVICE_NAMES = {"understand": "model", "geocode": "geocoding", "forecast": "forecast", "answer": "model"}
UNVERIFIED = " I could not verify this result."
UPSTREAM_ERRORS = (ProviderError, httpx.HTTPError, recording.NoRecording, BudgetExceeded)


def run(question: str, settings: Settings, client_id: str, client: httpx.Client | None = None, env: dict | None = None) -> Trace:
    """Run one request and return its trace. The trace is also kept in the store."""
    client = client or httpx.Client(timeout=30)
    env = config.ENV if env is None else env
    t = trace.new_trace(question, client_id, asdict(settings))
    budget = CallBudget()
    try:
        if _before_guardrails(question, client_id, t):
            _main_steps(question, settings, t, budget, client, env)
    except UPSTREAM_ERRORS as exc:
        _fail(t, exc)
    t.add_guardrail("model_call_budget", "around", "pass", f"{budget.used} of {budget.limit} model calls used")
    _mark_replays(t)
    t.finish()
    trace.STORE.add(t)
    return t


def _before_guardrails(question: str, client_id: str, t: Trace) -> bool:
    ok, detail = guardrails.check_length(question)
    t.add_guardrail("input_length", "before", _outcome(ok), detail)
    if not ok:
        return _finish(t, "input_too_long")
    ok, detail = guardrails.LIMITER.allow(client_id)
    t.add_guardrail("rate_limit", "before", _outcome(ok), detail)
    if not ok:
        return _finish(t, "rate_limited")
    return True


def _main_steps(question: str, settings: Settings, t: Trace, budget: CallBudget, client: httpx.Client, env: dict) -> None:
    understanding = _understand_step(question, settings, t, budget, client, env)
    if understanding.place is None:
        _finish(t, "no_place" if understanding.asked_forecast else "not_weather")
        return
    selection = _geocode_step(understanding.place, settings, t, client)
    if selection.outcome == "not_found":
        _finish(t, "place_not_found", name=understanding.place["name"])
        return
    if selection.outcome == "ambiguous":
        t.suggestions = answer.suggestions(selection.candidates)
        _finish(t, "place_ambiguous", name=understanding.place["name"], candidates=selection.candidates)
        return
    facts = _forecast_step(selection.place, understanding.when, settings, t, client)
    if facts is None:
        return
    _answer_step(question, facts, settings, t, budget, client, env)
    _after_guardrails(t, facts)


def _understand_step(question: str, settings: Settings, t: Trace, budget: CallBudget, client: httpx.Client, env: dict) -> understand.Understanding:
    started_at = trace.now_iso()
    response, understanding, source = understand.understand(question, settings.understand, budget, settings.offline, client, env)
    result = {"tool_calls": [asdict(c) for c in understanding.raw_calls], "text": response.text, "notes": understanding.notes}
    t.add_step(_model_step("understand", settings.understand, started_at, response, source, result))
    unknown = understanding.unknown_tools
    t.add_guardrail("registered_tools", "around", _outcome(not unknown), f"ignored unknown tools: {unknown}" if unknown else "only registered tools were called")
    return understanding


def _geocode_step(place: dict, settings: Settings, t: Trace, client: httpx.Client) -> geocode.Selection:
    started_at, started = trace.now_iso(), time.perf_counter()
    raw, candidates, source = geocode.search(place["name"], settings.offline, client)
    selection = geocode.choose(candidates, place["name"], place["region"], place["country"])
    result = {
        "outcome": selection.outcome,
        "place": asdict(selection.place) if selection.place else None,
        "candidates": [asdict(c) for c in selection.candidates],
    }
    t.add_step(Step("geocode", "service", GEOCODE_HANDLER, started_at, _ms(started), geocode.build_request(place["name"]), raw, result, source=source))
    return selection


def _forecast_step(place: Candidate, when: When, settings: Settings, t: Trace, client: httpx.Client) -> dict | None:
    """Fetch and resolve. Returns the facts, or None when the date is out of range."""
    started_at, started = trace.now_iso(), time.perf_counter()
    request = forecast.build_request(place, when)
    try:
        forecast.precheck(when, datetime.now(timezone.utc).date())
        raw, source = forecast.fetch(place, when, settings.offline, client)
    except forecast.DateOutOfRange as exc:
        t.add_step(Step("forecast", "service", FORECAST_HANDLER, started_at, 0, request, None, {"reason": f"{exc.date} is outside the forecast window"}, source="skipped"))
        _finish(t, "date_out_of_range", date=exc.date)
        return None
    try:
        facts = forecast.facts(place, when, raw)
    except forecast.DateOutOfRange as exc:
        t.add_step(Step("forecast", "service", FORECAST_HANDLER, started_at, _ms(started), request, raw, {"reason": f"{exc.date} is not among the returned days"}, source=source))
        _finish(t, "date_out_of_range", date=exc.date)
        return None
    t.add_step(Step("forecast", "service", FORECAST_HANDLER, started_at, _ms(started), request, raw, {"when": facts["when"], "facts": facts}, source=source))
    return facts


def _answer_step(question: str, facts: dict, settings: Settings, t: Trace, budget: CallBudget, client: httpx.Client, env: dict) -> None:
    started_at = trace.now_iso()
    response, source = answer.phrase(question, facts, settings.answer, budget, settings.offline, client, env)
    t.add_step(_model_step("answer", settings.answer, started_at, response, source, {"text": response.text}))
    t.outcome = "weather"
    t.answer = response.text.strip()


def _after_guardrails(t: Trace, facts: dict) -> None:
    ok, detail = guardrails.check_grounding(t.answer, facts)
    t.add_guardrail("grounding", "after", _outcome(ok), detail)
    if not ok:
        t.answer += UNVERIFIED
    ok, detail = guardrails.check_leak(t.answer, SYSTEM_PROMPTS)
    t.add_guardrail("system_prompt_leak", "after", _outcome(ok), detail)
    if not ok:
        _finish(t, "blocked")


def _model_step(name: str, model_id: str, started_at: str, response: ModelResponse, source: str, result: dict) -> Step:
    return Step(
        name, "model", model_id, started_at, response.latency_ms, response.request, response.raw, result,
        response.input_tokens, response.output_tokens, pricing.cost(model_id, response.input_tokens, response.output_tokens), source,
    )


def _finish(t: Trace, outcome: str, **values: object) -> bool:
    """Set a template answer for a non-weather outcome. Returns False for the guardrail callers."""
    t.outcome = outcome
    t.answer = answer.template(outcome, **values)
    return False


def _fail(t: Trace, exc: Exception) -> None:
    failed = STEP_ORDER[min(len(t.steps), len(STEP_ORDER) - 1)]
    t.add_step(Step(failed, "model" if SERVICE_NAMES[failed] == "model" else "service", "", trace.now_iso(), error=repr(exc)[:2000]))
    t.outcome = "upstream_error"
    t.error = answer.template("upstream_error", service=SERVICE_NAMES[failed])
    t.error_detail = repr(exc)[:2000]


def _mark_replays(t: Trace) -> None:
    replayed = [s.name for s in t.steps if s.source == "replayed"]
    if replayed:
        t.notice = "Replayed from recordings: " + ", ".join(replayed) + "."


def _outcome(ok: bool) -> str:
    return "pass" if ok else "fail"


def _ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)
