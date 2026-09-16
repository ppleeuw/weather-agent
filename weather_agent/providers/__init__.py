"""Model providers: the registry and one call_model for both vendors.

Why REST with httpx instead of the vendor SDKs: the exact request body and the
raw response go into the trace unchanged, there are no hidden retries, and the
project keeps its four dependencies. A provider module only knows how to build
its request and read its response; recording, budget and errors live here.
"""
from __future__ import annotations

import time

import httpx

from weather_agent import recording
from weather_agent.providers import anthropic, mistral
from weather_agent.providers.types import BudgetExceeded, CallBudget, Model, ModelResponse, ProviderError, ToolCall

__all__ = ["MODELS", "BudgetExceeded", "CallBudget", "Model", "ModelResponse", "ProviderError", "ToolCall", "call_model"]

MODELS: dict[str, Model] = {
    "mistral-small-latest": Model("mistral-small-latest", "mistral", "Mistral Small 4"),
    "mistral-medium-latest": Model("mistral-medium-latest", "mistral", "Mistral Medium 3.5"),
    "claude-haiku-4-5": Model("claude-haiku-4-5", "anthropic", "Claude Haiku 4.5"),
    # Sonnet 5 thinks by default and bills thinking as output; low effort keeps
    # a two-sentence weather answer cheap. Haiku 4.5 rejects this field.
    "claude-sonnet-5": Model("claude-sonnet-5", "anthropic", "Claude Sonnet 5", {"output_config": {"effort": "low"}}),
}

KEY_NAMES = {"mistral": "MISTRAL_API_KEY", "anthropic": "ANTHROPIC_API_KEY"}
MODULES = {"mistral": mistral, "anthropic": anthropic}


def call_model(
    model_id: str,
    system: str,
    user_text: str,
    tools: list[dict] | None,
    budget: CallBudget,
    offline: bool,
    client: httpx.Client,
    env: dict,
) -> tuple[ModelResponse, str]:
    """Make one model call and return (response, source). Source is live or replayed."""
    budget.spend()
    model = MODELS[model_id]
    module = MODULES[model.provider]
    api_key = env.get(KEY_NAMES[model.provider], "")
    if not api_key and not offline:
        raise ProviderError(0, f"{KEY_NAMES[model.provider]} is not set")
    url, headers, body = module.build_request(model, system, user_text, tools, api_key)
    # The recording key and the trace hold url and body only, never the headers.
    request = {"provider": model.provider, "url": url, "body": body}

    def live() -> dict:
        response = client.post(url, headers=headers, json=body, timeout=60)
        if response.status_code >= 400:
            raise ProviderError(response.status_code, response.text)
        return response.json()

    started = time.perf_counter()
    raw, source = recording.fetch("model", request, live, offline)
    latency_ms = int((time.perf_counter() - started) * 1000)
    text, calls, input_tokens, output_tokens, stop_reason = module.parse_response(raw)
    return ModelResponse(text, calls, input_tokens, output_tokens, latency_ms, request, raw, stop_reason), source
