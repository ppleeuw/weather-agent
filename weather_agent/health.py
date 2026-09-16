"""Dependency checks behind the health dot.

Seven checks: both keys present, both provider APIs reachable with the key,
both Open-Meteo endpoints answering, and the number of recordings. The
network checks run in parallel threads so the dot never waits on a slow
provider, and the result is cached for a minute so the page can poll freely.
"""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass

import httpx

from weather_agent import VERSION, recording
from weather_agent.providers import KEY_NAMES, anthropic

CHECK_TIMEOUT_S = 5
CACHE_S = 60

NETWORK_CHECKS = {
    "mistral_api": ("https://api.mistral.ai/v1/models", "mistral"),
    "anthropic_api": ("https://api.anthropic.com/v1/models", "anthropic"),
    "open_meteo_geocoding": ("https://geocoding-api.open-meteo.com/v1/search?name=Paris&count=1", None),
    "open_meteo_forecast": ("https://api.open-meteo.com/v1/forecast?latitude=48.85&longitude=2.35&current=temperature_2m", None),
}

_cache: dict | None = None


@dataclass
class Check:
    name: str
    ok: bool
    latency_ms: int
    detail: str


def check_all(env: dict, client: httpx.Client, offline: bool, use_cache: bool = True) -> dict:
    """The health report, cached for CACHE_S seconds."""
    global _cache
    if use_cache and _cache and time.time() - _cache["_at"] < CACHE_S:
        return _cache
    checks = _key_checks(env) + _network_checks(env, client) + [_recordings_check()]
    _cache = {
        "status": _status(checks),
        "version": VERSION,
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "offline": offline,
        "checks": [asdict(c) for c in checks],
        "_at": time.time(),
    }
    return _cache


def _key_checks(env: dict) -> list[Check]:
    return [
        Check(f"{provider}_key", bool(env.get(key_name)), 0, f"{key_name} is set" if env.get(key_name) else f"{key_name} is missing")
        for provider, key_name in KEY_NAMES.items()
    ]


def _network_checks(env: dict, client: httpx.Client) -> list[Check]:
    with ThreadPoolExecutor(max_workers=len(NETWORK_CHECKS)) as pool:
        return list(pool.map(lambda item: _ping(item[0], item[1][0], item[1][1], env, client), NETWORK_CHECKS.items()))


def _ping(name: str, url: str, provider: str | None, env: dict, client: httpx.Client) -> Check:
    headers = _auth_headers(provider, env)
    started = time.perf_counter()
    try:
        response = client.get(url, headers=headers, timeout=CHECK_TIMEOUT_S)
        latency = int((time.perf_counter() - started) * 1000)
        return Check(name, response.status_code < 400, latency, f"HTTP {response.status_code}")
    except httpx.HTTPError as exc:
        latency = int((time.perf_counter() - started) * 1000)
        return Check(name, False, latency, type(exc).__name__)


def _auth_headers(provider: str | None, env: dict) -> dict:
    if provider == "mistral":
        return {"Authorization": f"Bearer {env.get('MISTRAL_API_KEY', '')}"}
    if provider == "anthropic":
        return {"x-api-key": env.get("ANTHROPIC_API_KEY", ""), "anthropic-version": anthropic.API_VERSION}
    return {}


def _recordings_check() -> Check:
    count = recording.count()
    return Check("recordings", True, 0, f"{count} recorded responses available for offline replay")


def _status(checks: list[Check]) -> str:
    """ok when everything passes, down when Open-Meteo is gone, degraded otherwise."""
    if all(c.ok for c in checks):
        return "ok"
    open_meteo = [c for c in checks if c.name.startswith("open_meteo")]
    if not any(c.ok for c in open_meteo):
        return "down"
    return "degraded"
