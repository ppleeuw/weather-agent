"""FastAPI application: the HTTP routes and the static front end.

Routes stay thin: parse the request, call one function from another module,
return its result. Behaviour lives in those modules so they can be tested
without HTTP and read without FastAPI knowledge. /api/ask answers 200 for
every outcome the pipeline produced, including rejections and upstream
errors; the body says which. Only malformed requests get a 4xx.
"""
from __future__ import annotations

import threading
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from weather_agent import VERSION, config, health, pipeline, pricing, providers, trace
from weather_agent.eval import runner

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

app = FastAPI(title="Weather Agent", version=VERSION)
app.state.client = httpx.Client(timeout=30)  # one outbound client for the whole app


class AskBody(BaseModel):
    question: str


class EvalBody(BaseModel):
    model: str  # a model id, or "all"


# One eval run at a time; the page polls this while it runs. The lock makes "is one
# running?" and "now one is running" a single step, because FastAPI serves this sync
# route from several threads at once.
eval_state: dict = {"running": False, "done": 0, "total": 0, "model": ""}
eval_lock = threading.Lock()


@app.post("/api/ask")
def ask(body: AskBody, request: Request) -> dict:
    client_id = request.client.host if request.client else "unknown"
    t = pipeline.run(body.question, config.current_settings(), client_id, client=app.state.client)
    return {
        "ok": t.outcome not in {"upstream_error", "blocked"},
        "answer": t.answer,
        "suggestions": t.suggestions,
        "notice": t.notice,
        "outcome": t.outcome,
        "trace_id": t.id,
        "latency_ms": t.totals.latency_ms,
        "cost_usd": t.totals.cost_usd,
        "error": t.error,
        "models": {"understand": t.settings["understand"], "answer": t.settings["answer"]},
    }


@app.get("/api/settings")
def get_settings() -> dict:
    return _settings_body()


@app.put("/api/settings")
def put_settings(changes: dict) -> JSONResponse:
    try:
        config.update_settings(changes)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    return JSONResponse(_settings_body())


@app.get("/api/trace")
def latest_trace() -> dict:
    t = trace.STORE.latest()
    if t is None:
        raise HTTPException(status_code=404, detail="No request yet.")
    return t.to_dict()


@app.get("/api/trace/{trace_id}")
def one_trace(trace_id: str) -> dict:
    t = trace.STORE.get(trace_id)
    if t is None:
        raise HTTPException(status_code=404, detail="That trace is no longer kept.")
    return t.to_dict()


@app.get("/api/health")
def get_health() -> dict:
    report = health.check_all(config.ENV, app.state.client, config.current_settings().offline)
    return {key: value for key, value in report.items() if not key.startswith("_")}


@app.get("/api/cost")
def get_cost() -> dict:
    latest = trace.STORE.latest()
    return {
        "prices": [{"model": model_id, "label": providers.MODELS[model_id].label, **price} for model_id, price in pricing.PRICES.items()],
        "checked_on": pricing.CHECKED_ON,
        "last_request": _cost_of(latest) if latest else None,
        "session_total_usd": trace.STORE.session_cost(),
        "last_eval": {model: result["summary"]["total_cost_usd"] for model, result in runner.latest_per_model().items()} or None,
    }


@app.post("/api/eval/run", status_code=202)
def start_eval(body: EvalBody) -> JSONResponse:
    """Start a run in a background thread. The page polls GET /api/eval for progress and results."""
    models = list(config.OPTIONS["understand"]) if body.model == "all" else [body.model]
    if any(model not in config.OPTIONS["understand"] for model in models):
        return JSONResponse({"error": f"unknown model {body.model!r}"}, status_code=400)
    with eval_lock:
        if eval_state["running"]:
            return JSONResponse({"error": "An eval run is already in progress."}, status_code=409)
        eval_state.update(running=True, done=0, total=len(models) * len(runner.GOLDEN), model=models[0])
    threading.Thread(target=_run_eval_models, args=(models,), daemon=True).start()
    return JSONResponse({"models": models}, status_code=202)


@app.get("/api/eval")
def get_eval() -> dict:
    return {
        "running": eval_state["running"],
        "progress": {"done": eval_state["done"], "total": eval_state["total"], "model": eval_state["model"]},
        "latest": runner.latest_per_model(),
    }


@app.get("/api/eval/{run_id}")
def one_eval(run_id: str) -> dict:
    result = runner.load(run_id)
    if result is None:
        raise HTTPException(status_code=404, detail="No saved run with that id.")
    return result


def _run_eval_models(models: list[str]) -> None:
    """Runs in a background thread: one model after the other, saving each report."""
    finished_items = 0
    try:
        for model in models:
            eval_state["model"] = model

            def progress(done: int, total: int) -> None:
                eval_state["done"] = finished_items + done

            result = runner.run_eval(model, config.current_settings(), client=app.state.client, progress=progress)
            runner.save(result)
            finished_items += len(runner.GOLDEN)
    finally:
        eval_state.update(running=False, model="")


def _settings_body() -> dict:
    current = config.current_settings()
    return {
        "understand": current.understand,
        "geocode": current.geocode,
        "forecast": current.forecast,
        "answer": current.answer,
        "offline": current.offline,
        "options": config.OPTIONS,
    }


def _cost_of(t: trace.Trace) -> dict:
    return {
        "trace_id": t.id,
        "question": t.question,
        "cost_usd": t.totals.cost_usd,
        "steps": [
            {"name": s.name, "handler": s.handler, "cost_usd": s.cost_usd, "input_tokens": s.input_tokens, "output_tokens": s.output_tokens}
            for s in t.steps
        ],
    }


# Mounted last so that the /api routes above win over static files.
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
