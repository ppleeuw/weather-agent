"""Record every live service and model response, and replay it when needed.

Why: the demo must never depend on wifi (CLAUDE.md). Each request is keyed by
a hash of its canonical JSON, so the same question replays the same response.
Offline mode forces replay. Live mode falls back to a recording only when the
network itself fails, and the caller marks that step as replayed in the trace.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import httpx

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


class NoRecording(Exception):
    """Offline mode asked for a request that was never recorded."""


def key_for(request: dict) -> str:
    """Stable 16-character key: the same request content gives the same key."""
    canonical = json.dumps(request, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def fetch(
    kind: str,
    request: dict,
    live: Callable[[], dict],
    offline: bool,
    root: Path | None = None,
) -> tuple[dict, str]:
    """Return (response, source), where source is "live" or "replayed"."""
    path = (root or FIXTURES) / kind / f"{key_for(request)}.json"
    if offline:
        if not path.exists():
            raise NoRecording(f"no recording for {kind} request {path.stem}")
        return _load(path), "replayed"
    try:
        response = live()
    except httpx.TransportError:
        # The network failed. A recording keeps the demo alive.
        if path.exists():
            return _load(path), "replayed"
        raise
    _save(path, request, response)
    return response, "live"


def count(root: Path | None = None) -> int:
    """How many recordings exist; shown by the health check."""
    root = root or FIXTURES
    return sum(1 for _ in root.rglob("*.json")) if root.exists() else 0


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))["response"]


def _save(path: Path, request: dict, response: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "request": request,
        "response": response,
        "recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    path.write_text(json.dumps(record, indent=1, ensure_ascii=False), encoding="utf-8")
