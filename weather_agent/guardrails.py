"""Guardrails around the model steps.

Before the model: an input length cap and a per-client rate limit, so no
oversized or runaway input reaches a model. After the model: a grounding
check, which verifies that every number in the answer exists in the tool
results, and a leak check, which blocks answers that repeat the system prompt.
The model-call budget and the registered-tools check live in the provider and
understand modules, where those events happen. Every check returns
(ok, detail) so the pipeline can record a trace event either way.
"""
from __future__ import annotations

import re
import time
from collections import defaultdict, deque
from datetime import date, datetime
from typing import Iterator

MAX_INPUT_CHARS = 500
RATE_LIMIT = 60
RATE_WINDOW_S = 60
TOLERANCE = 0.5  # the model may round to the nearest whole number, nothing else
MIN_SENTENCE_CHARS = 30

# "12:00" becomes "12" so a time is checked as an hour, not as two numbers.
TIME_RE = re.compile(r"\b(\d{1,2}):(\d{2})\b")
# A number, optionally negative, with a decimal point or a decimal comma.
NUMBER_RE = re.compile(r"(?<!\w)-?\d+(?:[.,]\d+)?")


def check_length(question: str) -> tuple[bool, str]:
    length = len(question)
    return length <= MAX_INPUT_CHARS, f"{length} of {MAX_INPUT_CHARS} characters"


class RateLimiter:
    """Sliding window: at most `limit` requests per client in `window_s` seconds."""

    def __init__(self, limit: int = RATE_LIMIT, window_s: int = RATE_WINDOW_S) -> None:
        self.limit = limit
        self.window_s = window_s
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, client_id: str, now: float | None = None) -> tuple[bool, str]:
        now = time.time() if now is None else now
        hits = self._hits[client_id]
        while hits and hits[0] <= now - self.window_s:
            hits.popleft()
        if len(hits) >= self.limit:
            return False, f"{len(hits)} requests in the last {self.window_s} s, limit {self.limit}"
        hits.append(now)
        return True, f"{len(hits)} of {self.limit} requests in the last {self.window_s} s"


LIMITER = RateLimiter()


def numbers_in(text: str) -> list[float]:
    """Every number written in the text, times reduced to their hour."""
    text = TIME_RE.sub(r"\1", text)
    return [float(match.replace(",", ".")) for match in NUMBER_RE.findall(text)]


def allowed_numbers(facts: dict) -> set[float]:
    """Every number the answer may contain: values, date parts, hours, day count."""
    allowed = set(_numbers_in_json(facts))
    when = facts.get("when") or {}
    allowed.update(when.get("hours") or [])
    allowed.add(float(len(when.get("dates") or [])))
    return allowed


def check_grounding(answer: str, facts: dict) -> tuple[bool, str]:
    allowed = allowed_numbers(facts)
    found = numbers_in(answer)
    unmatched = [n for n in found if not any(abs(n - a) <= TOLERANCE for a in allowed)]
    if unmatched:
        return False, "numbers not in the tool results: " + ", ".join(_show(n) for n in unmatched)
    return True, f"{len(found)} numbers checked against {len(allowed)} values"


def check_leak(answer: str, system_prompts: list[str]) -> tuple[bool, str]:
    """Fail when a whole sentence of a system prompt appears in the answer."""
    haystack = _normalise(answer)
    for prompt in system_prompts:
        for sentence in re.split(r"[.!?\n]+", prompt):
            needle = _normalise(sentence)
            if len(needle) >= MIN_SENTENCE_CHARS and needle in haystack:
                return False, f"answer repeats a system prompt sentence: {needle[:60]}"
    return True, "no system prompt text in the answer"


def _numbers_in_json(value: object) -> Iterator[float]:
    if isinstance(value, bool):
        return
    if isinstance(value, (int, float)):
        yield float(value)
    elif isinstance(value, str):
        yield from _date_parts(value)
    elif isinstance(value, dict):
        for item in value.values():
            yield from _numbers_in_json(item)
    elif isinstance(value, list):
        for item in value:
            yield from _numbers_in_json(item)


def _date_parts(text: str) -> Iterator[float]:
    """Day, month, year and hour of an ISO date or datetime string, else nothing."""
    try:
        moment = datetime.fromisoformat(text) if "T" in text else datetime.combine(date.fromisoformat(text), datetime.min.time())
    except ValueError:
        return
    yield from (float(moment.day), float(moment.month), float(moment.year), float(moment.hour))


def _normalise(text: str) -> str:
    return " ".join(text.lower().split())


def _show(number: float) -> str:
    return str(int(number)) if number.is_integer() else str(number)
