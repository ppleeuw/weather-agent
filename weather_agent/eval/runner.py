"""Run the golden set against one model and save the report.

The model under test takes the two model steps; the service steps keep their
defaults. The runner calls the pipeline function directly, not HTTP, and
gives every item its own client id so the rate limit never fires. Each run is
saved as JSON, traces included, so the Eval page can show the last result
without running anything.
"""
from __future__ import annotations

import json
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from uuid import uuid4

import httpx

from weather_agent import VERSION, pipeline
from weather_agent.config import Settings
from weather_agent.eval import checks
from weather_agent.eval.golden import GOLDEN, GoldenItem
from weather_agent.providers import MODELS

RESULTS_DIR = Path(__file__).resolve().parent / "results"
Progress = Callable[[int, int], None]


def run_eval(
    model_id: str,
    settings: Settings,
    client: httpx.Client | None = None,
    env: dict | None = None,
    progress: Progress | None = None,
    items: list[GoldenItem] | None = None,
) -> dict:
    """Run every golden item through the pipeline with this model and report per layer."""
    under_test = replace(settings, understand=model_id, answer=model_id)
    golden = items if items is not None else GOLDEN
    started_at = _now()
    run_id = f"{started_at.strftime('%Y%m%d-%H%M%S')}-{model_id}"
    results = []
    for number, item in enumerate(golden, start=1):
        trace = pipeline.run(item.question, under_test, client_id=f"eval-{uuid4().hex[:8]}", client=client, env=env)
        layers = checks.check_item(item, trace)
        results.append({
            "id": item.id,
            "question": item.question[:80],
            "outcome": trace.outcome,
            "answer": trace.answer,
            "layers": [asdict(layer) for layer in layers],
            "latency_ms": trace.totals.latency_ms,
            "cost_usd": trace.totals.cost_usd,
            "trace": trace.to_dict(),
        })
        if progress:
            progress(number, len(golden))
    return {
        "run_id": run_id,
        "model": model_id,
        "label": MODELS[model_id].label,
        "started_at": started_at.isoformat(timespec="seconds"),
        "finished_at": _now().isoformat(timespec="seconds"),
        "version": VERSION,
        "summary": summarise(results),
        "failures": failures_of(results),
        "items": results,
    }


def summarise(results: list[dict]) -> dict:
    """Pass rates per layer as passed over applicable, plus mean latency and cost."""
    summary: dict = {}
    for layer in checks.LAYERS:
        applicable = [l for r in results for l in r["layers"] if l["layer"] == layer and l["applicable"]]
        summary[layer] = {"passed": sum(1 for l in applicable if l["passed"]), "applicable": len(applicable)}
    count = max(len(results), 1)
    summary["mean_latency_ms"] = round(sum(r["latency_ms"] for r in results) / count)
    summary["mean_cost_usd"] = round(sum(r["cost_usd"] for r in results) / count, 6)
    summary["total_cost_usd"] = round(sum(r["cost_usd"] for r in results), 6)
    return summary


def failures_of(results: list[dict]) -> list[dict]:
    return [
        {"item": r["id"], "question": r["question"], "layer": l["layer"], "reason": l["reason"]}
        for r in results
        for l in r["layers"]
        if l["applicable"] and not l["passed"]
    ]


def save(result: dict, directory: Path | None = None) -> Path:
    directory = directory or RESULTS_DIR  # resolved at call time so tests can point elsewhere
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{result['run_id']}.json"
    path.write_text(json.dumps(result, indent=1, ensure_ascii=False), encoding="utf-8")
    return path


def load(run_id: str, directory: Path | None = None) -> dict | None:
    path = (directory or RESULTS_DIR) / f"{run_id}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def latest_per_model(directory: Path | None = None) -> dict[str, dict]:
    """The newest saved run per model, without the per-item traces."""
    latest: dict[str, dict] = {}
    for path in sorted((directory or RESULTS_DIR).glob("*.json")):
        result = json.loads(path.read_text(encoding="utf-8"))
        if result["model"] not in latest or result["finished_at"] > latest[result["model"]]["finished_at"]:
            latest[result["model"]] = {key: value for key, value in result.items() if key != "items"}
    return latest


def print_report(results: list[dict]) -> None:
    """The command-line table: one row per model, then every failure."""
    print(f"{'model':<24} {'tools':>7} {'usage':>7} {'ground':>7} {'rules':>7} {'latency':>9} {'cost':>10}")
    for result in results:
        s = result["summary"]
        cells = [f"{s[layer]['passed']}/{s[layer]['applicable']}" for layer in checks.LAYERS]
        print(f"{result['model']:<24} {cells[0]:>7} {cells[1]:>7} {cells[2]:>7} {cells[3]:>7} {s['mean_latency_ms']:>6} ms ${s['mean_cost_usd']:.6f}")
    for result in results:
        for failure in result["failures"]:
            print(f"  {result['model']} item {failure['item']} [{failure['layer']}] {failure['reason']}")


def _now() -> datetime:
    return datetime.now(timezone.utc)
