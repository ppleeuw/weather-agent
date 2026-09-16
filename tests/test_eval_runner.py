import json
from pathlib import Path

import httpx

from weather_agent import config
from weather_agent.eval import runner
from weather_agent.eval.golden import GOLDEN

FIX = Path(__file__).parent / "fixtures"
ENV = {"MISTRAL_API_KEY": "m", "ANTHROPIC_API_KEY": "a"}


def tool_response():
    calls = [{"id": "aaaaaaaaa", "function": {"name": "lookup_place", "arguments": json.dumps({"name": "Paris"})}},
             {"id": "bbbbbbbbb", "function": {"name": "get_forecast", "arguments": json.dumps({"when": "now", "aspects": ["temperature"]})}}]
    return {"choices": [{"message": {"content": None, "tool_calls": calls}, "finish_reason": "tool_calls"}], "usage": {"prompt_tokens": 300, "completion_tokens": 40}}


def text_response(text):
    return {"choices": [{"message": {"content": text, "tool_calls": None}, "finish_reason": "stop"}], "usage": {"prompt_tokens": 500, "completion_tokens": 20}}


def make_client():
    state = {"calls": 0}

    def handler(request):
        host = request.url.host
        if host == "geocoding-api.open-meteo.com":
            return httpx.Response(200, json=json.loads((FIX / "geocode_paris.json").read_text()))
        if host == "api.open-meteo.com":
            return httpx.Response(200, json=json.loads((FIX / "forecast_paris_now.json").read_text()))
        state["calls"] += 1
        return httpx.Response(200, json=tool_response() if state["calls"] % 2 == 1 else text_response("It is 99 °C in Paris right now."))

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_run_eval_reports_layers_and_saves(tmp_path, monkeypatch):
    monkeypatch.setattr(runner.pipeline.recording, "FIXTURES", tmp_path / "fixtures")
    subset = [GOLDEN[0], GOLDEN[14]]  # Paris and the too-long input
    seen = []
    result = runner.run_eval("mistral-small-latest", config.DEFAULT_SETTINGS, client=make_client(), env=ENV,
                             progress=lambda done, total: seen.append((done, total)), items=subset)
    summary = result["summary"]
    assert seen == [(1, 2), (2, 2)] and result["model"] == "mistral-small-latest" and result["label"]
    assert summary["tools"] == {"passed": 2, "applicable": 2}
    assert summary["grounding"] == {"passed": 0, "applicable": 1}  # 99 °C is not in the facts
    assert any(f["layer"] == "grounding" and f["item"] == 1 for f in result["failures"])
    assert summary["total_cost_usd"] > 0 and len(result["items"]) == 2 and "trace" in result["items"][0]

    path = runner.save(result, tmp_path / "results")
    assert path.exists() and runner.load(result["run_id"], tmp_path / "results")["model"] == "mistral-small-latest"
    latest = runner.latest_per_model(tmp_path / "results")
    assert set(latest) == {"mistral-small-latest"} and "items" not in latest["mistral-small-latest"]


def test_print_report_runs(capsys):
    fake = {"model": "m", "summary": {layer: {"passed": 1, "applicable": 1} for layer in ["tools", "usage", "grounding", "rules"]} | {"mean_latency_ms": 5, "mean_cost_usd": 0.0}, "failures": [{"item": 1, "layer": "rules", "reason": "x"}]}
    runner.print_report([fake])
    out = capsys.readouterr().out
    assert "1/1" in out and "item 1 [rules] x" in out
