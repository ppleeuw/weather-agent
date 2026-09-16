"""Look a place name up and pick one result in code.

Two providers, one candidate shape and one selection rule. Open-Meteo Geocoding
is the default: it returns population and timezone. Nominatim (OpenStreetMap) is
the alternative: it ranks by an importance score, knows no timezone, and its
usage policy allows one request per second with an identifying User-Agent.

Why: the model only names the place the user mentioned. Deciding which "Paris"
or "Springfield" they meant is a lookup with fixed rules (spec section 4.2), so
it lives here as plain code and never in a prompt. Every lookup goes through
recording.fetch so the demo replays the same answer without network.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

import httpx

from weather_agent import recording

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
# The policy wants a User-Agent that names the application, not the HTTP library.
NOMINATIM_USER_AGENT = "weather-agent/1.1 (https://github.com/ppleeuw/weather-agent)"
NOMINATIM_MIN_INTERVAL_S = 1.1  # the policy allows one request per second
TIMEOUT_S = 10  # both services answer in well under a second; ten seconds covers a slow link
# A runner-up scoring at least this share of the top makes the name ambiguous. Population
# halves quickly between a city and its namesakes; importance is a compressed score where
# a ten percent gap already separates Paris from Paris, Texas.
AMBIGUITY_RATIOS = {"open-meteo-geocoding": 0.5, "nominatim": 0.9}
# GeoNames codes populated places PPL, PPLA, PPLC and so on; Nominatim was asked for settlements.
POPULATED_CODES = ("PPL", "settlement")
# How many places the user is offered when the name is ambiguous.
SUGGESTIONS = 3

_last_nominatim_call = 0.0


@dataclass
class Candidate:
    """One geocoding result, reduced to the fields the pipeline needs."""

    name: str
    admin1: str
    country: str
    country_code: str
    latitude: float
    longitude: float
    timezone: str  # empty when the provider does not know it; the forecast then asks Open-Meteo
    population: int
    feature_code: str
    score: float = 0.0  # what the provider ranks by: population for Open-Meteo, importance for Nominatim


@dataclass
class Selection:
    """What the selection rule decided: one place, a shortlist, or nothing."""

    outcome: str  # "place" | "place_ambiguous" | "place_not_found", the trace uses the same words
    place: Candidate | None = None
    candidates: list[Candidate] = field(default_factory=list)


def build_request(name: str, region: str | None = None, country: str | None = None, provider: str = "open-meteo-geocoding") -> dict:
    """The request as a plain dict, so recording can hash it as a key."""
    if provider == "nominatim":
        # Nominatim searches free text, so the region and country go into the query.
        query = ", ".join(part for part in (name, region, country) if part)
        params = {"q": query, "format": "jsonv2", "limit": 10, "addressdetails": 1, "extratags": 1,
                  "featureType": "settlement", "accept-language": "en"}
        return {"url": NOMINATIM_URL, "params": params}
    params = {"name": name, "count": 10, "language": "en", "format": "json"}
    return {"url": GEOCODING_URL, "params": params}


def search(
    name: str, region: str | None, country: str | None, offline: bool, client: httpx.Client, provider: str = "open-meteo-geocoding"
) -> tuple[dict, dict, list[Candidate], str]:
    """Return the request, the raw response, its candidates and "live" or "replayed"."""
    request = build_request(name, region, country, provider)

    def live() -> dict:
        if provider == "nominatim":
            _wait_for_nominatim()
        headers = {"User-Agent": NOMINATIM_USER_AGENT} if provider == "nominatim" else {}
        response = client.get(request["url"], params=request["params"], headers=headers, timeout=TIMEOUT_S)
        # A 400 raises httpx.HTTPStatusError; the pipeline maps it.
        response.raise_for_status()
        return response.json()

    raw, source = recording.fetch("geocode", request, live, offline)
    candidates = parse_nominatim(raw) if provider == "nominatim" else parse(raw)
    return request, raw, candidates, source


def _wait_for_nominatim() -> None:
    """Sleep so that live Nominatim calls stay at least one second apart."""
    global _last_nominatim_call
    wait = NOMINATIM_MIN_INTERVAL_S - (time.monotonic() - _last_nominatim_call)
    if wait > 0:
        time.sleep(wait)
    _last_nominatim_call = time.monotonic()


def parse(raw: dict) -> list[Candidate]:
    """Turn the raw Open-Meteo response into candidates. No results key means no results."""
    return [_candidate(result) for result in raw.get("results", [])]


def parse_nominatim(raw: list) -> list[Candidate]:
    """Turn the raw Nominatim response, a list, into candidates."""
    return [_nominatim_candidate(result) for result in raw]


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
        score=result.get("population") or 0,
    )


def _nominatim_candidate(result: dict) -> Candidate:
    address = result.get("address", {})
    population = result.get("extratags", {}).get("population", "")
    return Candidate(
        name=result.get("name") or address.get("city") or address.get("town") or address.get("village") or "",
        admin1=address.get("state", ""),
        country=address.get("country", ""),
        country_code=address.get("country_code", "").upper(),
        latitude=float(result["lat"]),
        longitude=float(result["lon"]),
        timezone="",  # Nominatim has no timezone; forecast.build_request asks Open-Meteo for it
        population=int(population) if str(population).isdigit() else 0,
        feature_code="settlement",
        score=float(result.get("importance") or 0),
    )


def choose(
    candidates: list[Candidate], name: str, region: str | None, country: str | None, provider: str = "open-meteo-geocoding"
) -> Selection:
    """Apply the selection rule of spec 4.2, one helper per step, in order."""
    remaining = populated_only(candidates)
    remaining = exact_name_first(remaining, name)
    remaining = filter_region(remaining, region)
    remaining = filter_country(remaining, country)
    remaining = merge_duplicates(remaining)
    remaining.sort(key=lambda candidate: candidate.score, reverse=True)
    if not remaining:
        return Selection("place_not_found")
    if is_ambiguous(remaining, AMBIGUITY_RATIOS[provider]):
        return Selection("place_ambiguous", candidates=remaining[:SUGGESTIONS])
    return Selection("place", place=remaining[0])


def populated_only(candidates: list[Candidate]) -> list[Candidate]:
    """Step 1: keep towns and cities; airports and parks named Atlantis go."""
    return [c for c in candidates if c.feature_code.startswith(POPULATED_CODES)]


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


# Country names people use that differ from the code or the GeoNames name.
COUNTRY_ALIASES = {"usa": "us", "u.s.": "us", "america": "us", "uk": "gb", "england": "gb", "holland": "nl"}


def filter_country(candidates: list[Candidate], country: str | None) -> list[Candidate]:
    """Step 3b: "US", "United States" and "Netherlands" all match their country.

    A code matches exactly. A name matches when one contains the other, so
    "Netherlands" finds "The Netherlands"; names under four characters are
    treated as codes so "US" never matches inside "Belarus".
    """
    if not country:
        return candidates
    wanted = country.strip().lower()
    wanted = COUNTRY_ALIASES.get(wanted, wanted)
    return [c for c in candidates if _country_matches(c, wanted)]


def _country_matches(candidate: Candidate, wanted: str) -> bool:
    name = candidate.country.lower()
    if wanted == candidate.country_code.lower() or wanted == name:
        return True
    return len(wanted) > 3 and (wanted in name or name in wanted)


def merge_duplicates(candidates: list[Candidate]) -> list[Candidate]:
    """Step 4: a provider sometimes lists one town twice; keep the higher-scoring entry."""
    best: dict[tuple[str, str, str], Candidate] = {}
    for candidate in candidates:
        key = (candidate.name, candidate.admin1, candidate.country)
        if key not in best or candidate.score > best[key].score:
            best[key] = candidate
    return list(best.values())


def is_ambiguous(ranked: list[Candidate], ratio: float) -> bool:
    """Step 6: Springfield MO (170k) versus MA (154k) is a coin toss;
    Paris (2.1M) versus Paris, Texas (25k) is not. Expects score order."""
    if len(ranked) < 2:
        return False
    return ranked[1].score >= ratio * ranked[0].score
