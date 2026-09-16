"""Anthropic Messages API over REST.

Request and response shapes follow https://platform.claude.com/docs/en/api/messages
as read on 2026-09-16. No temperature is sent: current Claude models reject it.
Thinking blocks may appear in the content; they carry no text here and are ignored.
"""
from __future__ import annotations

from weather_agent.providers.types import Model, ToolCall

URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"


def build_request(model: Model, system: str, user_text: str, tools: list[dict] | None, api_key: str) -> tuple[str, dict, dict]:
    """Return (url, headers, body) for one message."""
    headers = {"x-api-key": api_key, "anthropic-version": API_VERSION, "content-type": "application/json"}
    body: dict = {
        "model": model.id,
        "max_tokens": 1024,
        "system": system,
        "messages": [{"role": "user", "content": user_text}],
    }
    if tools:
        body["tools"] = [{"name": t["name"], "description": t["description"], "input_schema": t["input_schema"]} for t in tools]
        body["tool_choice"] = {"type": "auto"}
    body.update(model.extras)
    return URL, headers, body


def parse_response(raw: dict) -> tuple[str, list[ToolCall], int, int, str]:
    """Return (text, tool_calls, input_tokens, output_tokens, stop_reason)."""
    texts: list[str] = []
    calls: list[ToolCall] = []
    for block in raw.get("content", []):
        if block["type"] == "text":
            texts.append(block["text"])
        elif block["type"] == "tool_use":
            calls.append(ToolCall(block["id"], block["name"], dict(block.get("input") or {})))
    usage = raw.get("usage", {})
    return "".join(texts), calls, usage.get("input_tokens", 0), usage.get("output_tokens", 0), raw.get("stop_reason", "")
