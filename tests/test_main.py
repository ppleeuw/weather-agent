import httpx
from fastapi.testclient import TestClient

from weather_agent import VERSION, config, health
from weather_agent.main import app


def test_health_reports_version(monkeypatch):
    monkeypatch.setattr(health, "_cache", None)
    app.state.client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200)))
    body = TestClient(app).get("/api/health").json()
    assert body["version"] == VERSION and body["status"] in {"ok", "degraded", "down"} and "_at" not in body


def test_root_serves_index():
    response = TestClient(app).get("/")
    assert response.status_code == 200 and "<title>" in response.text


def test_settings_round_trip():
    client = TestClient(app)
    before = client.get("/api/settings").json()
    assert before["options"]["geocode"] == ["open-meteo-geocoding"]
    after = client.put("/api/settings", json={"understand": "claude-haiku-4-5"}).json()
    assert after["understand"] == "claude-haiku-4-5" and after["answer"] == before["answer"]
    client.put("/api/settings", json={"understand": before["understand"]})


def test_settings_rejects_unknown_handler():
    response = TestClient(app).put("/api/settings", json={"understand": "gpt-99"})
    assert response.status_code == 400 and "gpt-99" in response.json()["error"]


def test_cost_lists_four_prices():
    body = TestClient(app).get("/api/cost").json()
    assert len(body["prices"]) == 4 and body["checked_on"] == "2026-09-16" and "session_total_usd" in body


def test_unknown_trace_is_404():
    assert TestClient(app).get("/api/trace/nope").status_code == 404


def test_ask_rejects_long_input_with_ok_body():
    body = TestClient(app).post("/api/ask", json={"question": "x" * 600}).json()
    assert body["ok"] is True and body["outcome"] == "input_too_long" and body["trace_id"]
    assert TestClient(app).get("/api/trace").json()["outcome"] == "input_too_long"


def test_eval_status_and_unknown_run(monkeypatch, tmp_path):
    from weather_agent.eval import runner

    monkeypatch.setattr(runner, "RESULTS_DIR", tmp_path)
    client = TestClient(app)
    body = client.get("/api/eval").json()
    assert body["running"] is False and body["latest"] == {} and body["progress"]["total"] == 0
    assert client.get("/api/eval/nope").status_code == 404
    assert client.post("/api/eval/run", json={"model": "gpt-99"}).status_code == 400
