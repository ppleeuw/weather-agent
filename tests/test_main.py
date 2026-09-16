import httpx
from fastapi.testclient import TestClient

from weather_agent import VERSION, config, health
from weather_agent.main import app


def test_health_reports_version(monkeypatch):
    monkeypatch.setattr(health, "_cache", None)
    monkeypatch.setattr(app.state, "client", httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200))))
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


def test_eval_run_accepts_and_saves(monkeypatch, tmp_path):
    from types import SimpleNamespace

    from weather_agent import main
    from weather_agent.eval import runner

    monkeypatch.setattr(runner, "RESULTS_DIR", tmp_path)

    def fake_run_eval(model, settings, client=None, env=None, progress=None, items=None):
        return {"run_id": f"20260916-120000-{model}", "model": model, "label": "x", "finished_at": "2026-09-16T12:00:00+00:00",
                "summary": {"total_cost_usd": 0.0}, "failures": [], "items": []}

    class InlineThread:
        def __init__(self, target, args=(), daemon=False):
            self.target, self.args = target, args

        def start(self):
            self.target(*self.args)

    monkeypatch.setattr(runner, "run_eval", fake_run_eval)
    monkeypatch.setattr(main, "threading", SimpleNamespace(Thread=InlineThread, Lock=main.threading.Lock))
    client = TestClient(app)
    response = client.post("/api/eval/run", json={"model": "claude-haiku-4-5"})
    assert response.status_code == 202 and response.json() == {"models": ["claude-haiku-4-5"]}
    state = client.get("/api/eval").json()
    assert state["running"] is False and state["latest"]["claude-haiku-4-5"]["run_id"] == "20260916-120000-claude-haiku-4-5"
    assert client.get("/api/eval/20260916-120000-claude-haiku-4-5").status_code == 200
    assert client.get("/api/cost").json()["last_eval"] == {"claude-haiku-4-5": 0.0}
