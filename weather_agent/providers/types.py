"""Shared types for the model providers.

Why a separate module: both provider clients and the registry need these
records, and keeping them here avoids an import cycle between the package
and its provider modules.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# Output cap sent to both providers. Answers and tool calls stay under 100 tokens
# (largest recorded: 69), but Anthropic requires the field, and on Sonnet 5 the cap
# also covers the default thinking; effort "low" keeps that short.
MAX_TOKENS = 1024
MODEL_TIMEOUT_S = 60  # a slow model call is still a call; the pipeline has no retries


@dataclass(frozen=True)
class Model:
    """One entry of the model registry."""

    id: str
    provider: str  # mistral | anthropic
    label: str
    extras: dict = field(default_factory=dict)  # provider-specific request fields


@dataclass
class ToolCall:
    """One tool the model asked for, with parsed arguments."""

    id: str
    name: str
    arguments: dict


@dataclass
class ModelResponse:
    """What one model call returned, in provider-neutral form."""

    text: str
    tool_calls: list[ToolCall]
    input_tokens: int
    output_tokens: int
    latency_ms: int
    request: dict  # url and body only; headers carry the key and are never kept
    raw: dict
    stop_reason: str


class ProviderError(Exception):
    """The provider answered with an error status, or a key is missing."""

    def __init__(self, status: int, body: str) -> None:
        super().__init__(f"provider error {status}: {body[:200]}")
        self.status = status
        self.body = body


class BudgetExceeded(Exception):
    """A request tried to make more model calls than the guardrail allows."""


@dataclass
class CallBudget:
    """Counts model calls in one request.

    The assignment allows four. The pipeline makes exactly two, so the guard
    only fires if a future change adds calls or retries; then it stops a runaway
    request and the trace shows a failed guardrail instead of a bill.
    """

    limit: int = 4
    used: int = 0

    def spend(self) -> None:
        if self.used >= self.limit:
            raise BudgetExceeded(f"more than {self.limit} model calls in one request")
        self.used += 1
