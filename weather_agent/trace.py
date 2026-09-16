"""The trace: everything that happened during one request.

Why: every request must be explainable end to end, from the prompt through
each tool call and raw result to the final answer, with tokens, latency and
cost per step. The pipeline fills a Trace as it runs; the Trace page shows it.
The store keeps the last few traces in memory; nothing is written to disk.
"""
from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from uuid import uuid4

from weather_agent import VERSION


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class GuardrailEvent:
    """One guardrail evaluation, pass or fail, and the rule that fired."""

    rule: str
    stage: str  # before | around | after
    outcome: str  # pass | fail
    detail: str
    at: str


@dataclass
class Step:
    """One pipeline step: a model call, a service call, or pure code."""

    name: str  # understand | geocode | forecast | answer
    kind: str  # model | service | code
    handler: str  # model id or service name
    started_at: str
    latency_ms: int = 0
    request: dict | None = None
    response: dict | None = None
    result: dict | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    source: str = "live"  # live | replayed | skipped
    error: str | None = None


@dataclass
class Totals:
    latency_ms: int = 0
    cost_usd: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    model_calls: int = 0


@dataclass
class Trace:
    id: str
    version: str
    started_at: str
    question: str
    client_id: str
    settings: dict
    steps: list[Step] = field(default_factory=list)
    guardrails: list[GuardrailEvent] = field(default_factory=list)
    outcome: str = ""
    answer: str = ""
    suggestions: list[str] = field(default_factory=list)
    notice: str = ""
    error: str = ""
    error_detail: str = ""
    totals: Totals = field(default_factory=Totals)

    def add_step(self, step: Step) -> None:
        self.steps.append(step)

    def add_guardrail(self, rule: str, stage: str, outcome: str, detail: str) -> None:
        self.guardrails.append(GuardrailEvent(rule, stage, outcome, detail, now_iso()))

    def finish(self) -> None:
        """Sum the steps into the totals. Called once, at the end of a request."""
        totals = Totals()
        for step in self.steps:
            totals.latency_ms += step.latency_ms
            totals.cost_usd += step.cost_usd
            totals.input_tokens += step.input_tokens
            totals.output_tokens += step.output_tokens
            if step.kind == "model" and step.source != "skipped":
                totals.model_calls += 1
        totals.cost_usd = round(totals.cost_usd, 6)
        self.totals = totals

    def to_dict(self) -> dict:
        return asdict(self)


def new_trace(question: str, client_id: str, settings: dict) -> Trace:
    return Trace(
        id=uuid4().hex[:12],
        version=VERSION,
        started_at=now_iso(),
        question=question,
        client_id=client_id,
        settings=settings,
    )


class TraceStore:
    """The last few traces, newest last. Old ones fall off the front."""

    def __init__(self, keep: int = 20) -> None:
        self._traces: deque[Trace] = deque(maxlen=keep)
        self.session_cost_usd = 0.0  # every trace ever added, not only the kept ones

    def add(self, trace: Trace) -> None:
        self._traces.append(trace)
        self.session_cost_usd = round(self.session_cost_usd + trace.totals.cost_usd, 6)

    def latest(self) -> Trace | None:
        return self._traces[-1] if self._traces else None

    def get(self, trace_id: str) -> Trace | None:
        return next((t for t in self._traces if t.id == trace_id), None)

    def session_cost(self) -> float:
        return self.session_cost_usd


STORE = TraceStore()
