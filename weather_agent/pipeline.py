"""The pipeline: one request from question to answer, fully traced.

Order: guardrails before, understand (model), geocode (service), forecast
(service), answer (model), guardrails after. Each step appends to the trace.
Any failure inside a step becomes a friendly outcome with the full detail in
the trace; the request boundary never lets an exception escape as a bare 500.
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
from weather_agent.providers import BudgetExceeded, CallBudget, ModelResponse
from weather_agent.trace import Step, Trace

SYSTEM_PROMPTS = [understand.SYSTEM_PROMPT, answer.SYSTEM_PROMPT]
# Every _x_step appends exactly one Step after its call returns, so the number of
# steps in the trace says which step was running when an exception escaped.
STEP_ORDER = ["understand", "geocode", "forecast", "answer"]
STEP_KINDS = {"understand": "model", "geocode": "service", "forecast": "service", "answer": "model"}
SERVICE_NAMES = {"understand": "model", "geocode": "geocoding", "forecast": "forecast", "answer": "model"}
# Failures where no call was made, so the failed step is recorded as skipped.
NOT_CALLED = (recording.NoRecording, BudgetExceeded)
UNVERIFIED = " I could not verify this result."


def run(question: str, settings: Settings, client_id: str, client: httpx.Client | None = None,
        env: dict | None = None, keep: bool = True) -> Trace:
    """Run one request and return its trace. With keep, the trace also goes into the store."""
    client = client or httpx.Client()
    env = config.ENV if env is None else env
    # The trace keeps at most the allowed length of a question, so an oversized
    # input is rejected without being stored whole. The guardrail detail has the real length.
    t = trace.new_trace(question[:guardrails.MAX_INPUT_CHARS], client_id, asdict(settings))
    budget = CallBudget()
    exceeded = False
    try:
        if _before_guardrails(question, client_id, t):
            _main_steps(question, settings, t, budget, client, env)
    except BudgetExceeded as exc:
        exceeded = True
        _fail(t, exc, settings)
    except Exception as exc:  # provider, network or recording failures; anything else is still traced
        _fail(t, exc, settings)
    t.add_guardrail("model_call_budget", "around", _outcome(not exceeded), f"{budget.used} of {budget.limit} model calls used")
    _mark_replays(t)
    t.finish()
    if keep:
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
        _finish(t, "no_place" if understanding.asked_weather else "not_weather")
        return
    selection = _geocode_step(understanding.place, settings, t, client)
    if selection.outcome == "place_not_found":
        _finish(t, "place_not_found", name=understanding.place.name)
        return
    if selection.outcome == "place_ambiguous":
        t.suggestions = answer.suggestions(selection.candidates)
        _finish(t, "place_ambiguous", name=understanding.place.name, candidates=selection.candidates)
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


def _geocode_step(place: understand.Place, settings: Settings, t: Trace, client: httpx.Client) -> geocode.Selection:
    started_at, started = trace.now_iso(), time.perf_counter()
    request, raw, candidates, source = geocode.search(place.name, place.region, place.country, settings.offline, client, settings.geocode)
    selection = geocode.choose(candidates, place.name, place.region, place.country, settings.geocode)
    result = {
        "outcome": selection.outcome,
        "place": asdict(selection.place) if selection.place else None,
        "candidates": [asdict(c) for c in selection.candidates],
    }
    t.add_step(Step("geocode", "service", settings.geocode, started_at, _ms(started), request, raw, result, source=source))
    return selection


def _forecast_step(place: Candidate, when: When, settings: Settings, t: Trace, client: httpx.Client) -> dict | None:
    """Fetch and resolve. Returns the facts, or None when the date is out of range."""
    started_at, started = trace.now_iso(), time.perf_counter()
    request = forecast.build_request(place, when)
    try:
        forecast.precheck(when, datetime.now(timezone.utc).date())
        raw, source = forecast.fetch(place, when, settings.offline, client)
    except forecast.DateOutOfRange as exc:
        t.add_step(Step("forecast", "service", settings.forecast, started_at, 0, request, None, {"reason": f"{exc.date} is outside the forecast window"}, source="skipped"))
        _finish(t, "date_out_of_range", date=exc.date)
        return None
    try:
        facts = forecast.facts(place, when, raw)
    except forecast.DateOutOfRange as exc:
        t.add_step(Step("forecast", "service", settings.forecast, started_at, _ms(started), request, raw, {"reason": f"{exc.date} is not among the returned days"}, source=source))
        _finish(t, "date_out_of_range", date=exc.date)
        return None
    t.add_step(Step("forecast", "service", settings.forecast, started_at, _ms(started), request, raw, {"when": facts["when"], "facts": facts}, source=source))
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
        name, "model", model_id, started_at, response.latency_ms, response.request, response.raw,
        {**result, "stop_reason": response.stop_reason},
        response.input_tokens, response.output_tokens, pricing.cost(model_id, response.input_tokens, response.output_tokens), source,
    )


def _finish(t: Trace, outcome: str, **values: object) -> bool:
    """Set a template answer for a non-weather outcome. Returns False for the guardrail callers."""
    t.outcome = outcome
    t.answer = answer.template(outcome, **values)
    return False


def _fail(t: Trace, exc: Exception, settings: Settings) -> None:
    """Record the step that was running, then a friendly sentence with the detail kept in the trace."""
    failed = STEP_ORDER[min(len(t.steps), len(STEP_ORDER) - 1)]
    not_called = isinstance(exc, NOT_CALLED)
    t.add_step(Step(failed, STEP_KINDS[failed], getattr(settings, failed), trace.now_iso(),
                    source="skipped" if not_called else "live", error=repr(exc)[:2000]))
    t.error_detail = repr(exc)[:2000]
    if isinstance(exc, recording.NoRecording):
        _finish(t, "no_recording")
        return
    t.outcome = "upstream_error"
    t.error = answer.template("upstream_error", service=SERVICE_NAMES[failed])


def _mark_replays(t: Trace) -> None:
    replayed = [s.name for s in t.steps if s.source == "replayed"]
    if replayed:
        t.notice = "Replayed from recordings: " + ", ".join(replayed) + "."


def _outcome(ok: bool) -> str:
    return "pass" if ok else "fail"


def _ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)
