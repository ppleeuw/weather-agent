"""Look a place name up with Open-Meteo Geocoding and pick one result in code.

Why: the model only names the place the user mentioned. Deciding which "Paris"
or "Springfield" they meant is a lookup with fixed rules (spec section 4.2), so
it lives here as plain code and never in a prompt. Every lookup goes through
recording.fetch so the demo replays the same answer without network.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import httpx

from weather_agent import recording

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
# A runner-up with at least half the top population makes the name ambiguous.
AMBIGUITY_RATIO = 0.5
# How many places the user is offered when the name is ambiguous.
SUGGESTIONS = 3


@dataclass
class Candidate:
    """One geocoding result, reduced to the fields the pipeline needs."""

    name: str
    admin1: str
    country: str
    country_code: str
    latitude: float
    longitude: float
    timezone: str
    population: int
    feature_code: str


@dataclass
class Selection:
    """What the selection rule decided: one place, a shortlist, or nothing."""

    outcome: str  # "place" | "ambiguous" | "not_found"
    place: Candidate | None = None
    candidates: list[Candidate] = field(default_factory=list)


def build_request(name: str) -> dict:
    """The request as a plain dict, so recording can hash it as a key."""
    params = {"name": name, "count": 10, "language": "en", "format": "json"}
    return {"url": GEOCODING_URL, "params": params}


def search(name: str, offline: bool, client: httpx.Client) -> tuple[dict, list[Candidate], str]:
    """Return the raw response, its candidates and "live" or "replayed"."""
    request = build_request(name)

    def live() -> dict:
        response = client.get(request["url"], params=request["params"], timeout=10)
        # A 400 from Open-Meteo raises httpx.HTTPStatusError; the pipeline maps it.
        response.raise_for_status()
        return response.json()

    raw, source = recording.fetch("geocode", request, live, offline)
    return raw, parse(raw), source


def parse(raw: dict) -> list[Candidate]:
    """Turn the raw response into candidates. No results key means no results."""
    return [_candidate(result) for result in raw.get("results", [])]


def _candidate(result: dict) -> Candidate:
    # Coordinates are indexed directly: a result without them is unusable.
    return Candidate(
        name=result.get("name", ""),
        admin1=result.get("admin1", ""),
        country=result.get("country", ""),
        country_code=result.get("country_code", ""),
        latitude=result["latitude"],
        longitude=result["longitude"],
        timezone=result.get("timezone", ""),
        population=result.get("population") or 0,  # absent or null both mean unknown
        feature_code=result.get("feature_code", ""),
    )


def choose(
    candidates: list[Candidate], name: str, region: str | None, country: str | None
) -> Selection:
    """Apply the selection rule of spec 4.2, one helper per step, in order."""
    remaining = populated_only(candidates)
    remaining = exact_name_first(remaining, name)
    remaining = filter_region(remaining, region)
    remaining = filter_country(remaining, country)
    remaining = merge_duplicates(remaining)
    remaining.sort(key=lambda candidate: candidate.population, reverse=True)
    if not remaining:
        return Selection("not_found")
    if is_ambiguous(remaining):
        return Selection("ambiguous", candidates=remaining[:SUGGESTIONS])
    return Selection("place", place=remaining[0])


def populated_only(candidates: list[Candidate]) -> list[Candidate]:
    """Step 1: GeoNames codes towns and cities PPL, PPLA, PPLC and so on."""
    return [c for c in candidates if c.feature_code.startswith("PPL")]


def exact_name_first(candidates: list[Candidate], name: str) -> list[Candidate]:
    """Step 2: when "Paris" itself is present, near misses like "Saint Paris" go."""
    wanted = name.strip().lower()
    exact = [c for c in candidates if c.name.lower() == wanted]
    return exact or candidates


def filter_region(candidates: list[Candidate], region: str | None) -> list[Candidate]:
    """Step 3a: "Texas" keeps Paris, Texas. A substring test, so "Île-de-France"
    also matches the API's longer "Île-de-France Region"."""
    if not region:
        return candidates
    return [c for c in candidates if region.lower() in c.admin1.lower()]


def filter_country(candidates: list[Candidate], country: str | None) -> list[Candidate]:
    """Step 3b: the user may say "US" or "United States"; both are accepted."""
    if not country:
        return candidates
    wanted = country.lower()
    return [
        c for c in candidates if c.country.lower() == wanted or c.country_code.lower() == wanted
    ]


def merge_duplicates(candidates: list[Candidate]) -> list[Candidate]:
    """Step 4: the API sometimes lists one town twice; keep the larger entry."""
    largest: dict[tuple[str, str, str], Candidate] = {}
    for candidate in candidates:
        key = (candidate.name, candidate.admin1, candidate.country)
        if key not in largest or candidate.population > largest[key].population:
            largest[key] = candidate
    return list(largest.values())


def is_ambiguous(ranked: list[Candidate]) -> bool:
    """Step 6: Springfield MO (170k) versus MA (154k) is a coin toss;
    Paris (2.1M) versus Paris, Texas (25k) is not. Expects population order."""
    if len(ranked) < 2:
        return False
    return ranked[1].population >= AMBIGUITY_RATIO * ranked[0].population
