"""Configuration: reads .env, holds the defaults and the current settings.

Why a hand-written .env reader: it is twelve lines and one dependency fewer
than python-dotenv. The real .env is read only here, at import time, and its
values are never logged or returned by any route.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env"


def load_env(path: Path) -> dict[str, str]:
    """Return the KEY=value pairs of a .env file. A missing file gives {}."""
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip("'\"")
    return values


ENV = load_env(ENV_FILE)

# Which handler may run each pipeline step. The two service steps have one
# option each on purpose: Open-Meteo was chosen for both, see the design spec.
MODEL_IDS = ["mistral-small-latest", "mistral-medium-latest", "claude-haiku-4-5", "claude-sonnet-5"]
OPTIONS: dict[str, list[str]] = {
    "understand": MODEL_IDS,
    "geocode": ["open-meteo-geocoding"],
    "forecast": ["open-meteo-forecast"],
    "answer": MODEL_IDS,
}


@dataclass(frozen=True)
class Settings:
    """The five choices the Models page exposes."""

    understand: str
    geocode: str
    forecast: str
    answer: str
    offline: bool


DEFAULT_SETTINGS = Settings(
    understand="mistral-medium-latest",
    geocode="open-meteo-geocoding",
    forecast="open-meteo-forecast",
    answer="mistral-medium-latest",
    offline=False,
)

_current = DEFAULT_SETTINGS  # in memory only; a restart returns to the defaults


def current_settings() -> Settings:
    return _current


def update_settings(changes: dict) -> Settings:
    """Apply a partial update after validating every value."""
    global _current
    for key, value in changes.items():
        if key == "offline":
            if not isinstance(value, bool):
                raise ValueError("offline must be true or false")
        elif key in OPTIONS:
            if value not in OPTIONS[key]:
                raise ValueError(f"{value!r} is not an option for {key}")
        else:
            raise ValueError(f"unknown setting {key!r}")
    _current = replace(_current, **changes)
    return _current
