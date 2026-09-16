"""Mistral chat completions over REST.

Request and response shapes follow https://docs.mistral.ai/api/ as read on
2026-09-16. Tool arguments arrive as a JSON string in the documented case and
as an object in the schema, so both are accepted.
"""
from __future__ import annotations

import json

from weather_agent.providers.types import MAX_TOKENS, Model, ProviderError, ToolCall

URL = "https://api.mistral.ai/v1/chat/completions"


def build_request(model: Model, system: str, user_text: str, tools: list[dict] | None, api_key: str) -> tuple[str, dict, dict]:
    """Return (url, headers, body) for one chat completion."""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    body: dict = {
        "model": model.id,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_text},
        ],
        "max_tokens": MAX_TOKENS,
    }
    if tools:
        body["tools"] = [
            {"type": "function", "function": {"name": t["name"], "description": t["description"], "parameters": t["input_schema"]}}
            for t in tools
        ]
        body["tool_choice"] = "auto"
    body.update(model.extras)
    return URL, headers, body


def parse_response(raw: dict) -> tuple[str, list[ToolCall], int, int, str]:
    """Return (text, tool_calls, input_tokens, output_tokens, finish_reason)."""
    choice = raw["choices"][0]
    message = choice["message"]
    calls = [
        ToolCall(call.get("id", ""), call["function"]["name"], _arguments(call["function"]["arguments"]))
        for call in (message.get("tool_calls") or [])
    ]
    usage = raw.get("usage", {})
    return _text(message.get("content")), calls, usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0), choice.get("finish_reason", "")


def _text(content: str | list | None) -> str:
    # Content is a string, null when only tools were called, or a list of chunks.
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    return "".join(chunk.get("text", "") for chunk in content if isinstance(chunk, dict))


def _arguments(value: str | dict | None) -> dict:
    """The model's arguments as a dict. Anything else is a provider error, never a crash."""
    if isinstance(value, str) and value:
        try:
            value = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ProviderError(200, f"tool call arguments are not valid JSON: {value[:100]}") from exc
    if value is None or value == "":
        return {}
    if not isinstance(value, dict):
        raise ProviderError(200, f"tool call arguments are not a JSON object: {str(value)[:100]}")
    return value
