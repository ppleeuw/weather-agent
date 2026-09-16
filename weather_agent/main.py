"""FastAPI application: the HTTP routes and the static front end.

Routes stay thin: parse the request, call one function from another module,
return its result. Behaviour lives in those modules so they can be tested
without HTTP and read without FastAPI knowledge.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from weather_agent import VERSION

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

app = FastAPI(title="Weather Agent", version=VERSION)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "version": VERSION}


# Mounted last so that the /api routes above win over static files.
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
