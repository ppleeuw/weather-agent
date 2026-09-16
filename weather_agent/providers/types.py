"""Shared types for the model providers.

Why a separate module: both provider clients and the registry need these
records, and keeping them here avoids an import cycle between the package
and its provider modules.
"""
from __future__ import annotations

from dataclasses import dataclass, field


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
    """Counts model calls in one request. The guardrail allows four."""

    limit: int = 4
    used: int = 0

    def spend(self) -> None:
        if self.used >= self.limit:
            raise BudgetExceeded(f"more than {self.limit} model calls in one request")
        self.used += 1
