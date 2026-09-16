import json

import httpx
import pytest

from weather_agent import providers
from weather_agent.providers import anthropic, mistral

TOOL = {"name": "lookup_place", "description": "d", "input_schema": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}}
ENV = {"MISTRAL_API_KEY": "m", "ANTHROPIC_API_KEY": "a"}


def test_mistral_request_shape():
    url, headers, body = mistral.build_request(providers.MODELS["mistral-small-latest"], "sys", "hi", [TOOL], "key")
    assert url.endswith("/v1/chat/completions") and headers["Authorization"] == "Bearer key"
    assert body["messages"][0] == {"role": "system", "content": "sys"} and body["tools"][0]["function"]["parameters"] == TOOL["input_schema"]


def test_mistral_parse_handles_string_arguments():
    raw = {"choices": [{"message": {"content": None, "tool_calls": [{"id": "abc123def", "function": {"name": "lookup_place", "arguments": "{\"name\": \"Paris\"}"}}]}, "finish_reason": "tool_calls"}], "usage": {"prompt_tokens": 10, "completion_tokens": 4}}
    text, calls, i, o, stop = mistral.parse_response(raw)
    assert calls[0].arguments == {"name": "Paris"} and (i, o, stop) == (10, 4, "tool_calls") and text == ""


def test_mistral_parse_handles_object_arguments_and_chunked_content():
    raw = {"choices": [{"message": {"content": [{"type": "text", "text": "a"}, {"type": "text", "text": "b"}], "tool_calls": [{"id": "x", "function": {"name": "f", "arguments": {"k": 1}}}]}, "finish_reason": "stop"}], "usage": {}}
    text, calls, i, o, stop = mistral.parse_response(raw)
    assert text == "ab" and calls[0].arguments == {"k": 1} and (i, o) == (0, 0)


def test_anthropic_request_shape_and_extras():
    url, headers, body = anthropic.build_request(providers.MODELS["claude-sonnet-5"], "sys", "hi", [TOOL], "key")
    assert headers["x-api-key"] == "key" and headers["anthropic-version"] == "2023-06-01"
    assert body["system"] == "sys" and body["tools"][0]["input_schema"] == TOOL["input_schema"] and body["output_config"] == {"effort": "low"}
    assert "temperature" not in body


def test_anthropic_parse_ignores_thinking_blocks():
    raw = {"content": [{"type": "thinking", "thinking": ""}, {"type": "text", "text": "ok"}, {"type": "tool_use", "id": "t1", "name": "lookup_place", "input": {"name": "Paris"}}], "stop_reason": "tool_use", "usage": {"input_tokens": 7, "output_tokens": 3}}
    text, calls, i, o, stop = anthropic.parse_response(raw)
    assert text == "ok" and calls[0].name == "lookup_place" and (i, o, stop) == (7, 3, "tool_use")


def test_call_model_records_request_without_headers(tmp_path, monkeypatch):
    def handler(request):
        return httpx.Response(200, json={"content": [{"type": "text", "text": "hi"}], "stop_reason": "end_turn", "usage": {"input_tokens": 1, "output_tokens": 1}})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(providers.recording, "FIXTURES", tmp_path)
    response, source = providers.call_model("claude-haiku-4-5", "s", "u", None, providers.CallBudget(), False, client, ENV)
    assert response.text == "hi" and source == "live" and "headers" not in response.request
    recorded = json.loads(next((tmp_path / "model").iterdir()).read_text())
    assert "x-api-key" not in json.dumps(recorded) and '"a"' not in json.dumps(recorded["request"])


def test_budget_blocks_fifth_call():
    b = providers.CallBudget()
    for _ in range(4):
        b.spend()
    with pytest.raises(providers.BudgetExceeded):
        b.spend()


def test_non_2xx_raises_provider_error():
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(401, text="bad key")))
    with pytest.raises(providers.ProviderError) as e:
        providers.call_model("mistral-small-latest", "s", "u", None, providers.CallBudget(), False, client, ENV)
    assert e.value.status == 401


def test_missing_key_raises_before_any_call():
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={})))
    with pytest.raises(providers.ProviderError) as e:
        providers.call_model("mistral-small-latest", "s", "u", None, providers.CallBudget(), False, client, {})
    assert "MISTRAL_API_KEY" in e.value.body


def test_mistral_rejects_arguments_that_are_not_an_object():
    raw = {"choices": [{"message": {"content": None, "tool_calls": [{"id": "x", "function": {"name": "f", "arguments": "[1, 2]"}}]}, "finish_reason": "stop"}], "usage": {}}
    with pytest.raises(providers.ProviderError):
        mistral.parse_response(raw)


def test_anthropic_rejects_tool_input_that_is_not_an_object():
    raw = {"content": [{"type": "tool_use", "id": "t1", "name": "f", "input": ["Paris"]}], "stop_reason": "tool_use", "usage": {}}
    with pytest.raises(providers.ProviderError):
        anthropic.parse_response(raw)
