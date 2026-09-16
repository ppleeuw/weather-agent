import json
from pathlib import Path

import httpx

from weather_agent import config, pipeline

FIX = Path(__file__).parent / "fixtures"
ENV = {"MISTRAL_API_KEY": "m", "ANTHROPIC_API_KEY": "a"}


def mistral_tool_response():
    calls = [
        {"id": "aaaaaaaaa", "function": {"name": "lookup_place", "arguments": json.dumps({"name": "Paris"})}},
        {"id": "bbbbbbbbb", "function": {"name": "get_forecast", "arguments": json.dumps({"when": "now", "aspects": ["temperature"]})}},
    ]
    return {"choices": [{"message": {"content": None, "tool_calls": calls}, "finish_reason": "tool_calls"}], "usage": {"prompt_tokens": 300, "completion_tokens": 40}}


def mistral_text_response(text):
    return {"choices": [{"message": {"content": text, "tool_calls": None}, "finish_reason": "stop"}], "usage": {"prompt_tokens": 500, "completion_tokens": 20}}


def make_client(answer_text, tool_response=None):
    state = {"model_calls": 0}

    def handler(request):
        host = request.url.host
        if host == "geocoding-api.open-meteo.com":
            return httpx.Response(200, json=json.loads((FIX / "geocode_paris.json").read_text()))
        if host == "api.open-meteo.com":
            return httpx.Response(200, json=json.loads((FIX / "forecast_paris_now.json").read_text()))
        state["model_calls"] += 1
        body = (tool_response or mistral_tool_response()) if state["model_calls"] == 1 else mistral_text_response(answer_text)
        return httpx.Response(200, json=body)

    return httpx.Client(transport=httpx.MockTransport(handler)), state


def settings():
    return config.DEFAULT_SETTINGS


def current_temperature(t):
    return t.steps[2].result["facts"]["current"]["temperature_2m"]


def test_weather_path_grounded(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline.recording, "FIXTURES", tmp_path)
    client, _ = make_client("PLACEHOLDER")
    # First run to learn the fixture temperature, then answer with it.
    first = pipeline.run("Hey, how cold is it in Paris?", settings(), "test", client=client, env=ENV)
    value = current_temperature(first)
    client, _ = make_client(f"It is {round(value)} °C in Paris right now.")
    t = pipeline.run("Hey, how cold is it in Paris?", settings(), "test", client=client, env=ENV)
    assert t.outcome == "weather" and "°C" in t.answer and t.notice == ""
    assert [s.name for s in t.steps] == ["understand", "geocode", "forecast", "answer"]
    assert t.totals.model_calls == 2 and t.totals.cost_usd > 0
    assert {g.rule for g in t.guardrails} >= {"input_length", "rate_limit", "registered_tools", "model_call_budget", "grounding", "system_prompt_leak"}
    assert "headers" not in t.steps[0].request


def test_ungrounded_answer_gets_notice(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline.recording, "FIXTURES", tmp_path)
    client, _ = make_client("It is 99 °C in Paris.")
    t = pipeline.run("How warm is it in Paris?", settings(), "test", client=client, env=ENV)
    assert t.answer.endswith("I could not verify this result.")
    assert any(g.rule == "grounding" and g.outcome == "fail" for g in t.guardrails)


def test_too_long_makes_no_model_call(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline.recording, "FIXTURES", tmp_path)
    client, state = make_client("x")
    t = pipeline.run("w" * 501, settings(), "test", client=client, env=ENV)
    assert t.outcome == "input_too_long" and state["model_calls"] == 0 and t.steps == []


def test_no_tools_is_not_weather(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline.recording, "FIXTURES", tmp_path)
    client, state = make_client("x", tool_response=mistral_text_response("NONE"))
    t = pipeline.run("Tell me a joke.", settings(), "test", client=client, env=ENV)
    assert t.outcome == "not_weather" and state["model_calls"] == 1 and "weather" in t.answer


def test_leaked_prompt_is_blocked(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline.recording, "FIXTURES", tmp_path)
    client, _ = make_client("You phrase weather facts for the user. Use only the values in the facts; add no other knowledge and no advice beyond the verdicts.")
    t = pipeline.run("How warm is it in Paris?", settings(), "test", client=client, env=ENV)
    assert t.outcome == "blocked" and t.answer == "I cannot show that answer."


def test_upstream_error_is_friendly_with_detail(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline.recording, "FIXTURES", tmp_path)
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(500, text="boom")))
    t = pipeline.run("How warm is it in Paris?", settings(), "test", client=client, env=ENV)
    assert t.outcome == "upstream_error" and "boom" in t.error_detail and t.error and t.steps[-1].error


def test_offline_replays_after_one_live_run(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline.recording, "FIXTURES", tmp_path)
    client, _ = make_client("It is 14 °C in Paris right now.")
    pipeline.run("How warm is it in Paris?", settings(), "test", client=client, env=ENV)
    offline = config.Settings("mistral-medium-latest", "open-meteo-geocoding", "open-meteo-forecast", "mistral-medium-latest", True)
    dead = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(500)))
    t = pipeline.run("How warm is it in Paris?", offline, "test", client=dead, env={})
    assert t.outcome == "weather" and all(s.source == "replayed" for s in t.steps) and "Replayed" in t.notice


def test_offline_without_recording_is_a_friendly_outcome(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline.recording, "FIXTURES", tmp_path)
    offline = config.Settings("mistral-medium-latest", "open-meteo-geocoding", "open-meteo-forecast", "mistral-medium-latest", True)
    dead = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(500)))
    t = pipeline.run("How warm is it in Paris?", offline, "test", client=dead, env={})
    assert t.outcome == "no_recording" and "recording" in t.answer and t.error == ""
    assert t.steps[0].name == "understand" and t.steps[0].source == "skipped" and t.steps[0].handler == "mistral-medium-latest"
    assert t.totals.model_calls == 1 and t.error_detail.startswith("NoRecording")


def test_malformed_tool_arguments_become_an_upstream_error(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline.recording, "FIXTURES", tmp_path)
    broken = {"choices": [{"message": {"content": None, "tool_calls": [{"id": "x", "function": {"name": "lookup_place", "arguments": "not json"}}]}, "finish_reason": "tool_calls"}], "usage": {}}
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=broken)))
    t = pipeline.run("How warm is it in Paris?", settings(), "test", client=client, env=ENV)
    assert t.outcome == "upstream_error" and "not valid JSON" in t.error_detail


def test_eval_traces_can_stay_out_of_the_store(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline.recording, "FIXTURES", tmp_path)
    before = pipeline.trace.STORE.latest()
    client, _ = make_client("It is 14 °C in Paris right now.")
    pipeline.run("How warm is it in Paris?", settings(), "test", client=client, env=ENV, keep=False)
    assert pipeline.trace.STORE.latest() is before
