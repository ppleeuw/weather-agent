# Weather Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A FastAPI web app where a natural-language weather question is understood by a model, answered from Open-Meteo data by code, phrased by a model, traced end to end, guarded, evaluated against a golden set, and demonstrable offline.

**Architecture:** Four pipeline steps: understand (model, native function calling, one round), geocode (Open-Meteo Geocoding), forecast (Open-Meteo Forecast plus date resolution in code), answer (model). Guardrails run before, around and after the model steps. Every step writes to a trace. Every service and model response is recorded so the app replays without network.

**Tech Stack:** Python 3.14, FastAPI, uvicorn, httpx, pytest. Frontend: plain HTML, CSS and JavaScript ES modules, no build step.

**Spec:** `docs/superpowers/specs/2026-09-16-weather-agent-design.md`. The plan argues from the spec; read both.

## Global Constraints

- Dependencies: exactly `fastapi`, `uvicorn`, `httpx`, `pytest` in `requirements.txt`. Nothing else without a one-line justification in the README.
- The model only understands the request and phrases the answer. Dates, timezones, units, validation, place selection and lookups are code.
- Never read, print, log or commit `.env`. Only `config.load_env()` reads it, at runtime. Headers with keys never enter a trace.
- Input cap 500 characters. Rate limit 60 per minute per client. At most 4 model calls per request.
- Temperatures in °C, wind in km/h, precipitation in mm, snowfall in cm, probability in %.
- Every step, pass or fail, is visible in the trace. Errors: one friendly sentence in the UI, full detail in the trace.
- Code style: type hints, dataclasses, module docstring, comments explain why, functions under 40 lines, files under 200 lines, English.
- Tests never touch the network: services use recorded fixtures, providers use `httpx.MockTransport`.
- One commit per task, message in imperative mood, ending with `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.
- Version bumps and tags at the end of each phase as listed in spec section 12.

## File structure

| File | Responsibility |
|---|---|
| `weather_agent/__init__.py` | `VERSION` |
| `weather_agent/config.py` | `load_env()`, `Settings` dataclass with the five choices, defaults, in-memory current settings |
| `weather_agent/recording.py` | `fetch(kind, request, live, offline)` record and replay |
| `weather_agent/geocode.py` | `search()`, `choose()`, `Candidate`, `Selection` |
| `weather_agent/forecast.py` | `Place`, `When`, `build_request()`, `fetch()`, `resolve()`, `facts()`, WMO table, verdicts |
| `weather_agent/trace.py` | `Trace`, `Step`, `GuardrailEvent`, `Totals`, `TraceStore` |
| `weather_agent/pricing.py` | `PRICES`, `cost()` |
| `weather_agent/providers/__init__.py` | `MODELS` registry, `ModelResponse`, `ToolCall`, `CallBudget`, `call_model()` |
| `weather_agent/providers/mistral.py` | `build_request()`, `parse_response()` |
| `weather_agent/providers/anthropic.py` | `build_request()`, `parse_response()` |
| `weather_agent/understand.py` | `SYSTEM_PROMPT`, `TOOLS`, `understand()`, `Understanding` |
| `weather_agent/answer.py` | `SYSTEM_PROMPT`, `phrase()`, `template()` |
| `weather_agent/guardrails.py` | `check_length()`, `RateLimiter`, `check_grounding()`, `check_leak()` |
| `weather_agent/pipeline.py` | `run()` ties the steps together and fills the trace |
| `weather_agent/health.py` | `check_all()` |
| `weather_agent/main.py` | FastAPI app and routes |
| `weather_agent/__main__.py` | `python -m weather_agent ask "..."` |
| `weather_agent/eval/golden.py` | `GoldenItem`, `GOLDEN` |
| `weather_agent/eval/checks.py` | layer checks and answer rules |
| `weather_agent/eval/runner.py` | `run_eval()`, results files, `__main__` entry |
| `static/index.html`, `styles.css`, `app.js`, `api.js`, `settings.js`, `pages/*.js`, `logo.svg`, `favicon.svg` | UI |
| `fixtures/geocode`, `fixtures/forecast`, `fixtures/model` | recordings |
| `tests/` | one test file per module |

---

## Phase 0: scaffold (v0.1.0)

### Task 1: Package, config and app shell

**Files:**
- Create: `requirements.txt`, `weather_agent/__init__.py`, `weather_agent/config.py`, `weather_agent/main.py`, `tests/test_config.py`, `tests/test_main.py`

**Interfaces:**
- Produces: `VERSION: str`; `load_env(path: Path) -> dict[str, str]`; `Settings` dataclass with fields `understand: str`, `geocode: str`, `forecast: str`, `answer: str`, `offline: bool`; `DEFAULT_SETTINGS`; `current_settings() -> Settings`; `update_settings(changes: dict) -> Settings`; `OPTIONS: dict[str, list[str]]` mapping each step to its allowed handler ids; FastAPI `app` serving `static/` at `/` and `GET /api/health` returning `{"status": "ok", "version": VERSION}` for now.

- [ ] **Step 1: Create the venv and requirements**

```bash
cd /home/ppleeuw/projects/weather-agent
printf 'fastapi\nuvicorn\nhttpx\npytest\n' > requirements.txt
python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt
```

- [ ] **Step 2: Write the failing tests**

```python
# tests/test_config.py
from pathlib import Path
from weather_agent import config

def test_load_env_reads_key_value_pairs_and_ignores_comments(tmp_path: Path):
    env = tmp_path / ".env"
    env.write_text("# comment\nMISTRAL_API_KEY=abc\n\nANTHROPIC_API_KEY = 'xyz'\n")
    assert config.load_env(env) == {"MISTRAL_API_KEY": "abc", "ANTHROPIC_API_KEY": "xyz"}

def test_load_env_missing_file_returns_empty(tmp_path: Path):
    assert config.load_env(tmp_path / "nope") == {}

def test_update_settings_rejects_unknown_handler():
    import pytest
    with pytest.raises(ValueError):
        config.update_settings({"understand": "not-a-model"})

def test_update_settings_changes_one_field_only():
    before = config.current_settings()
    after = config.update_settings({"offline": True})
    assert after.offline is True and after.understand == before.understand
    config.update_settings({"offline": False})
```

```python
# tests/test_main.py
from fastapi.testclient import TestClient
from weather_agent.main import app
from weather_agent import VERSION

def test_health_reports_version():
    client = TestClient(app)
    body = client.get("/api/health").json()
    assert body["version"] == VERSION

def test_root_serves_index():
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200 and "<title>" in response.text
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `.venv/bin/pytest -q`
Expected: import errors for `weather_agent`.

- [ ] **Step 4: Implement**

`weather_agent/__init__.py`: `VERSION = "0.1.0"`.

`weather_agent/config.py`: `load_env` reads lines, skips blanks and `#`, splits on the first `=`, strips whitespace and one pair of quotes, returns a dict; `load_env` is called once at import into `ENV` for `.env` in the project root and does not print anything. `OPTIONS = {"understand": list(MODEL_IDS), "geocode": ["open-meteo-geocoding"], "forecast": ["open-meteo-forecast"], "answer": list(MODEL_IDS)}` where `MODEL_IDS` is a literal list of the four ids for now (Task 7 replaces it with the registry). `DEFAULT_SETTINGS = Settings("mistral-medium-latest", "open-meteo-geocoding", "open-meteo-forecast", "mistral-medium-latest", False)`. `update_settings` validates each key against `OPTIONS` or bool for `offline`, raises `ValueError` otherwise, uses `dataclasses.replace`.

`weather_agent/main.py`: `app = FastAPI(title="Weather Agent")`, `GET /api/health` returns status and version, `app.mount("/", StaticFiles(directory=STATIC_DIR, html=True))` last. `static/index.html` is a minimal page with `<title>Weather Agent</title>` for now; Task 2 fills it.

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/pytest -q`
Expected: 6 passed.

- [ ] **Step 6: Commit**

```bash
git add requirements.txt weather_agent tests static/index.html
git commit -m "Add package skeleton, .env loader, settings and app shell"
```

### Task 2: Page shell, design tokens, logo

**Files:**
- Create: `static/index.html`, `static/styles.css`, `static/logo.svg`, `static/favicon.svg`

**Interfaces:**
- Produces: the DOM ids used by later JavaScript: `#question`, `#ask`, `#result`, `#answer`, `#meta`, `#suggestions`, `#empty`, `#error`, `#health-dot`, `#health-card`, `#gear`, `#settings`, `#settings-menu`, `#settings-page`, `#version`.

- [ ] **Step 1: Write `styles.css`**

Copy the `:root` tokens from `docs/DESIGN.md` verbatim. Add the type scale classes `.display`, `.heading`, `.body`, `.small`, `.label`, `.code`, the components from the DESIGN.md table as classes `.button-primary`, `.button-secondary`, `.input`, `.select`, `.card`, `.table`, `.menu-item`, `.badge`, `.spinner`, `.error`, `.empty`, and the layout: `.page` 960 px centred with 32 px padding, `.header` flex with the logo left and the controls right, `.modal-backdrop` fixed full-screen with `rgba(24,24,27,.4)`, `.modal` 960 px wide, max-height 80vh, grid with a 200 px menu column. Health dot: 10 px circle, colour by class `.ok`, `.degraded`, `.down` mapped to success, warning, error tokens. Transitions 120 ms on background and border colour only.

- [ ] **Step 2: Write `index.html`**

Header with `logo.svg`, the name "Weather Agent" in the heading style, the health dot button and the gear button. Main with the ask row, the result area containing spinner, answer, meta, suggestions, error, and the empty state with two secondary buttons carrying `data-question` attributes for the assignment questions. Footer with `#version`, "Weather data by Open-Meteo.com" linking to https://open-meteo.com/, "Location data based on GeoNames". The modal markup with the six menu items as buttons carrying `data-page` in the spec order. Google Fonts link for Instrument Serif and Inter, `<script type="module" src="/app.js">`.

- [ ] **Step 3: Draw the logo**

`logo.svg`, 32 by 32 viewBox: a rounded speech bubble outline in `#18181b`, stroke 2, with a filled sun disc `#fa500f` of radius 6 inside and a short tail bottom-left. `favicon.svg` is the same mark without the outline padding. Link the favicon in `index.html`.

- [ ] **Step 4: Check in the browser**

Run: `.venv/bin/uvicorn weather_agent.main:app --port 8000`
Expected: at http://127.0.0.1:8000 the header, empty state and footer render with the tokens; no console errors apart from the missing `app.js`.

- [ ] **Step 5: Commit and tag**

```bash
git add static
git commit -m "Add page shell with design tokens, logo and favicon"
git tag v0.1.0
```

---

## Phase 1: services (v0.2.0)

### Task 3: Recording

**Files:**
- Create: `weather_agent/recording.py`, `tests/test_recording.py`

**Interfaces:**
- Produces: `class NoRecording(Exception)`; `key_for(request: dict) -> str` (16 hex chars of SHA-256 over `json.dumps(request, sort_keys=True, ensure_ascii=False)`); `fetch(kind: str, request: dict, live: Callable[[], dict], offline: bool, root: Path = FIXTURES) -> tuple[dict, str]` returning `(response, source)` with source `"live"` or `"replayed"`; `count(root: Path = FIXTURES) -> int`.
- Behaviour: offline true reads `root/kind/key.json` or raises `NoRecording`. Offline false calls `live()`, writes `{request, response, recorded_at}` and returns live. If `live()` raises `httpx.TransportError` and a recording exists, return it as replayed; otherwise re-raise.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_recording.py
import httpx, pytest
from weather_agent import recording

def boom():
    raise httpx.ConnectError("no network")

def test_live_call_is_recorded_and_returned(tmp_path):
    response, source = recording.fetch("geocode", {"name": "Paris"}, lambda: {"ok": 1}, offline=False, root=tmp_path)
    assert (response, source) == ({"ok": 1}, "live")
    assert (tmp_path / "geocode" / f"{recording.key_for({'name': 'Paris'})}.json").exists()

def test_offline_replays_recording(tmp_path):
    recording.fetch("geocode", {"name": "Paris"}, lambda: {"ok": 1}, offline=False, root=tmp_path)
    assert recording.fetch("geocode", {"name": "Paris"}, boom, offline=True, root=tmp_path) == ({"ok": 1}, "replayed")

def test_offline_without_recording_raises(tmp_path):
    with pytest.raises(recording.NoRecording):
        recording.fetch("geocode", {"name": "Nowhere"}, boom, offline=True, root=tmp_path)

def test_transport_error_falls_back_to_recording(tmp_path):
    recording.fetch("forecast", {"lat": 1}, lambda: {"t": 2}, offline=False, root=tmp_path)
    assert recording.fetch("forecast", {"lat": 1}, boom, offline=False, root=tmp_path) == ({"t": 2}, "replayed")

def test_transport_error_without_recording_reraises(tmp_path):
    with pytest.raises(httpx.TransportError):
        recording.fetch("forecast", {"lat": 9}, boom, offline=False, root=tmp_path)

def test_key_is_order_independent():
    assert recording.key_for({"a": 1, "b": 2}) == recording.key_for({"b": 2, "a": 1})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_recording.py -q`
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement `recording.py`** as specified in Interfaces. `FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"`. Write with `json.dumps(indent=1, ensure_ascii=False)`. Use `datetime.now(timezone.utc).isoformat(timespec="seconds")` for `recorded_at`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_recording.py -q`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add weather_agent/recording.py tests/test_recording.py
git commit -m "Add request recording and replay"
```

### Task 4: Geocode

**Files:**
- Create: `weather_agent/geocode.py`, `tests/test_geocode.py`, `tests/fixtures/geocode_paris.json`, `tests/fixtures/geocode_springfield.json`, `tests/fixtures/geocode_empty.json`

**Interfaces:**
- Consumes: `recording.fetch`.
- Produces:
  - `@dataclass Candidate: name, admin1, country, country_code, latitude, longitude, timezone, population: int, feature_code`
  - `@dataclass Selection: outcome: str  # "place" | "ambiguous" | "not_found"; place: Candidate | None; candidates: list[Candidate]`
  - `build_request(name: str) -> dict` returning `{"url": GEOCODING_URL, "params": {"name": name, "count": 10, "language": "en", "format": "json"}}`
  - `search(name: str, offline: bool, client: httpx.Client) -> tuple[dict, list[Candidate], str]` returning raw response, candidates and source. Uses `recording.fetch("geocode", request, live, offline)`.
  - `choose(candidates: list[Candidate], name: str, region: str | None, country: str | None) -> Selection` implementing spec 4.2 steps 1 to 7 with `AMBIGUITY_RATIO = 0.5`.
  - `parse(raw: dict) -> list[Candidate]` with `population` defaulting to 0 and other missing fields to `""`.

- [ ] **Step 1: Save three fixtures** by running these once and saving the JSON bodies under `tests/fixtures/`:

```bash
curl -s "https://geocoding-api.open-meteo.com/v1/search?name=Paris&count=10&language=en&format=json" > tests/fixtures/geocode_paris.json
curl -s "https://geocoding-api.open-meteo.com/v1/search?name=Springfield&count=10&language=en&format=json" > tests/fixtures/geocode_springfield.json
curl -s "https://geocoding-api.open-meteo.com/v1/search?name=Qwxlorbia&count=10&language=en&format=json" > tests/fixtures/geocode_empty.json
```

- [ ] **Step 2: Write the failing tests**

```python
# tests/test_geocode.py
import json
from pathlib import Path
from weather_agent import geocode

FIX = Path(__file__).parent / "fixtures"
def load(name): return geocode.parse(json.loads((FIX / name).read_text()))

def test_parse_defaults_missing_population_to_zero():
    cands = geocode.parse({"results": [{"name": "X", "latitude": 1.0, "longitude": 2.0, "country_code": "ZZ", "timezone": "UTC", "feature_code": "PPL"}]})
    assert cands[0].population == 0 and cands[0].admin1 == ""

def test_parse_without_results_key_is_empty():
    assert geocode.parse({"generationtime_ms": 0.1}) == []

def test_paris_is_clear_and_picks_france():
    sel = geocode.choose(load("geocode_paris.json"), "Paris", None, None)
    assert sel.outcome == "place" and sel.place.country_code == "FR"

def test_paris_texas_uses_the_region_filter():
    sel = geocode.choose(load("geocode_paris.json"), "Paris", "Texas", None)
    assert sel.outcome == "place" and sel.place.admin1 == "Texas"

def test_springfield_is_ambiguous_with_three_suggestions():
    sel = geocode.choose(load("geocode_springfield.json"), "Springfield", None, None)
    assert sel.outcome == "ambiguous" and len(sel.candidates) == 3
    assert all(c.name.lower() == "springfield" for c in sel.candidates)

def test_empty_results_are_not_found():
    assert geocode.choose(load("geocode_empty.json"), "Qwxlorbia", None, None).outcome == "not_found"

def test_region_filter_with_no_match_is_not_found():
    assert geocode.choose(load("geocode_paris.json"), "Paris", "Bavaria", None).outcome == "not_found"

def test_country_filter_accepts_code_or_name():
    cands = load("geocode_paris.json")
    assert geocode.choose(cands, "Paris", None, "US").place.country_code == "US"
    assert geocode.choose(cands, "Paris", None, "France").place.country_code == "FR"

def test_non_populated_places_are_dropped():
    cands = [geocode.Candidate("Atlantis", "", "Italy", "IT", 0, 0, "Europe/Rome", 0, "AMUS")]
    assert geocode.choose(cands, "Atlantis", None, None).outcome == "not_found"

def test_build_request_shape():
    req = geocode.build_request("Paris")
    assert req["params"] == {"name": "Paris", "count": 10, "language": "en", "format": "json"}
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_geocode.py -q`
Expected: `ModuleNotFoundError`.

- [ ] **Step 4: Implement `geocode.py`.** Selection rule in this order, each step its own small function: `populated_only`, `exact_name_first`, `filter_region`, `filter_country`, `merge_duplicates`, then sort and the ratio test. `search` builds the request, defines `live()` as `client.get(url, params=params, timeout=10).raise_for_status().json()` and delegates to `recording.fetch`. A 400 from Open-Meteo raises `httpx.HTTPStatusError`; the pipeline maps it later.

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_geocode.py -q`
Expected: 10 passed.

- [ ] **Step 6: Commit**

```bash
git add weather_agent/geocode.py tests/test_geocode.py tests/fixtures
git commit -m "Add Open-Meteo geocoding with the place selection rule"
```

### Task 5: Forecast, date resolution, facts

**Files:**
- Create: `weather_agent/forecast.py`, `tests/test_forecast.py`, `tests/fixtures/forecast_paris_now.json`, `tests/fixtures/forecast_paris_daily.json`, `tests/fixtures/forecast_london_hourly.json`

**Interfaces:**
- Consumes: `geocode.Candidate`, `recording.fetch`.
- Produces:
  - `@dataclass When: kind: str; weekday: str | None = None; date: str | None = None; days: int | None = None; part_of_day: str | None = None; aspects: list[str] = field(default_factory=list)`
  - `class DateOutOfRange(Exception)` carrying `.date: str`
  - `precheck(when: When, today: date) -> None` raises `DateOutOfRange` for `kind == "date"` outside `[today - 1 day, today + 15 days]` at the given precision; `in_days` and `period` with `days` outside 1 to 15 raise `ValueError`.
  - `build_request(place: Candidate, when: When) -> dict` `{"url": FORECAST_URL, "params": {...}}` per spec 4.3.
  - `fetch(place, when, offline, client) -> tuple[dict, str]`.
  - `resolve(when: When, raw: dict) -> dict` returning `{"kind", "label", "dates": [...], "hours": [int] | None}`; raises `DateOutOfRange` when the date is not in `raw["daily"]["time"]`.
  - `facts(place: Candidate, when: When, raw: dict) -> dict` per spec 4.3, including `weather` text from `WMO_CODES` and `verdicts`.
  - `WMO_CODES: dict[int, str]` for codes 0, 1, 2, 3, 45, 48, 51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 71, 73, 75, 77, 80, 81, 82, 85, 86, 95, 96, 99.
  - Constants: `RAIN_YES = 50`, `RAIN_UNLIKELY = 20`, `WINDY_KMH = 20`.
  - `PART_OF_DAY_HOURS = {"morning": (6, 12), "afternoon": (12, 18), "evening": (18, 24), "night": (0, 6)}`.

- [ ] **Step 1: Save fixtures** with these calls, saving the bodies under `tests/fixtures/`:

```bash
B="https://api.open-meteo.com/v1/forecast?latitude=48.8566&longitude=2.3522&timezone=Europe%2FParis"
curl -s "$B&current=temperature_2m,apparent_temperature,relative_humidity_2m,precipitation,weather_code,wind_speed_10m,wind_gusts_10m,is_day&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max,precipitation_sum,weather_code&forecast_days=1" > tests/fixtures/forecast_paris_now.json
curl -s "$B&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max,precipitation_sum,snowfall_sum,weather_code,wind_speed_10m_max&forecast_days=16" > tests/fixtures/forecast_paris_daily.json
L="https://api.open-meteo.com/v1/forecast?latitude=51.5074&longitude=-0.1278&timezone=Europe%2FLondon"
curl -s "$L&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max,precipitation_sum,snowfall_sum,weather_code,wind_speed_10m_max&hourly=temperature_2m,precipitation_probability,precipitation,weather_code,wind_speed_10m&forecast_days=16" > tests/fixtures/forecast_london_hourly.json
```

- [ ] **Step 2: Write the failing tests**

```python
# tests/test_forecast.py
import json
from datetime import date
from pathlib import Path
import pytest
from weather_agent import forecast
from weather_agent.geocode import Candidate

FIX = Path(__file__).parent / "fixtures"
PARIS = Candidate("Paris", "Île-de-France", "France", "FR", 48.8566, 2.3522, "Europe/Paris", 2138551, "PPLC")
def raw(name): return json.loads((FIX / name).read_text())

def test_precheck_rejects_1950():
    with pytest.raises(forecast.DateOutOfRange):
        forecast.precheck(forecast.When("date", date="1950-01"), date(2026, 9, 16))

def test_precheck_accepts_a_date_in_the_window():
    forecast.precheck(forecast.When("date", date="2026-09-20"), date(2026, 9, 16))

def test_precheck_rejects_far_future():
    with pytest.raises(forecast.DateOutOfRange):
        forecast.precheck(forecast.When("date", date="2027-01-01"), date(2026, 9, 16))

def test_request_for_now_asks_current_block():
    params = forecast.build_request(PARIS, forecast.When("now"))["params"]
    assert "temperature_2m" in params["current"] and params["forecast_days"] == 1 and params["timezone"] == "Europe/Paris"

def test_request_for_tomorrow_asks_16_daily_days_without_hourly():
    params = forecast.build_request(PARIS, forecast.When("tomorrow"))["params"]
    assert params["forecast_days"] == 16 and "hourly" not in params and "current" not in params

def test_request_with_part_of_day_adds_hourly():
    params = forecast.build_request(PARIS, forecast.When("today", part_of_day="afternoon"))["params"]
    assert "precipitation_probability" in params["hourly"]

def test_resolve_tomorrow_is_second_local_date():
    r = raw("forecast_paris_daily.json")
    assert forecast.resolve(forecast.When("tomorrow"), r)["dates"] == [r["daily"]["time"][1]]

def test_resolve_weekday_picks_first_matching_day_today_included():
    r = raw("forecast_paris_daily.json")
    first = date.fromisoformat(r["daily"]["time"][0])
    name = first.strftime("%A").lower()
    assert forecast.resolve(forecast.When("weekday", weekday=name), r)["dates"] == [r["daily"]["time"][0]]

def test_resolve_period_returns_seven_dates():
    r = raw("forecast_paris_daily.json")
    assert len(forecast.resolve(forecast.When("period", days=7), r)["dates"]) == 7

def test_resolve_absent_date_raises():
    with pytest.raises(forecast.DateOutOfRange):
        forecast.resolve(forecast.When("date", date="1950-01-01"), raw("forecast_paris_daily.json"))

def test_resolve_afternoon_hours():
    r = raw("forecast_london_hourly.json")
    res = forecast.resolve(forecast.When("today", part_of_day="afternoon"), r)
    assert res["hours"] == [12, 13, 14, 15, 16, 17, 18]

def test_facts_for_now_have_current_and_weather_text():
    f = forecast.facts(PARIS, forecast.When("now"), raw("forecast_paris_now.json"))
    assert "temperature_2m" in f["current"] and isinstance(f["current"]["weather"], str)
    assert f["units"]["temperature"] == "°C" and f["place"]["timezone"] == "Europe/Paris"

def test_facts_daily_rows_carry_weekday_and_verdicts():
    f = forecast.facts(PARIS, forecast.When("tomorrow"), raw("forecast_paris_daily.json"))
    row = f["daily"][0]
    assert set(row) >= {"date", "weekday", "temperature_2m_max", "temperature_2m_min", "precipitation_probability_max"}
    assert f["verdicts"]["rain"] in {"yes", "unlikely", "no"}

def test_rain_verdict_thresholds():
    assert forecast.rain_verdict(50) == "yes" and forecast.rain_verdict(49) == "unlikely" and forecast.rain_verdict(19) == "no"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_forecast.py -q`
Expected: `ModuleNotFoundError`.

- [ ] **Step 4: Implement `forecast.py`.** Keep the variable lists as module constants `CURRENT_VARS`, `DAILY_VARS`, `HOURLY_VARS`. `facts` builds `current` only for `now`, `daily` rows for the resolved dates, `hourly` rows for the resolved hours on the first resolved date, `today = raw["daily"]["time"][0]`, verdicts from the selected rows: rain from `current.precipitation > 0` mapped to `yes` for now, otherwise the max of `precipitation_probability_max` over the selected days or of hourly `precipitation_probability` over the window; windy from `current.wind_speed_10m` or the max `wind_speed_10m_max`; snow from any `snowfall_sum > 0` with weekday names in `snow_days`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_forecast.py -q`
Expected: 14 passed.

- [ ] **Step 6: Commit and tag**

```bash
git add weather_agent/forecast.py tests/test_forecast.py tests/fixtures
git commit -m "Add Open-Meteo forecast with date resolution, facts and verdicts"
sed -i 's/VERSION = "0.1.0"/VERSION = "0.2.0"/' weather_agent/__init__.py
git commit -am "Release 0.2.0" && git tag v0.2.0
```

---

## Phase 2: models and pipeline (v0.3.0)

### Task 6: Trace and pricing

**Files:**
- Create: `weather_agent/trace.py`, `weather_agent/pricing.py`, `tests/test_trace.py`, `tests/test_pricing.py`

**Interfaces:**
- Produces in `trace.py`:
  - `@dataclass GuardrailEvent: rule: str; stage: str; outcome: str; detail: str; at: str`
  - `@dataclass Step: name: str; kind: str; handler: str; started_at: str; latency_ms: int = 0; request: dict | None = None; response: dict | None = None; result: dict | None = None; input_tokens: int = 0; output_tokens: int = 0; cost_usd: float = 0.0; source: str = "live"; error: str | None = None`
  - `@dataclass Totals: latency_ms: int = 0; cost_usd: float = 0.0; input_tokens: int = 0; output_tokens: int = 0; model_calls: int = 0`
  - `@dataclass Trace: id: str; version: str; started_at: str; question: str; client_id: str; settings: dict; steps: list[Step]; guardrails: list[GuardrailEvent]; outcome: str = ""; answer: str = ""; suggestions: list[str]; notice: str = ""; error: str = ""; error_detail: str = ""; totals: Totals`
  - `new_trace(question, client_id, settings) -> Trace` with `id = uuid4().hex[:12]`.
  - `Trace.add_step(step)`, `Trace.add_guardrail(rule, stage, outcome, detail)`, `Trace.finish()` computing totals from steps, `Trace.to_dict()` via `dataclasses.asdict`.
  - `class TraceStore: keep: int = 20; add(trace); latest() -> Trace | None; get(id) -> Trace | None; session_cost() -> float`. Module-level `STORE = TraceStore()`.
  - `now_iso() -> str` UTC with seconds.
- Produces in `pricing.py`: `PRICES: dict[str, dict]` with keys `input_usd_per_mtok`, `output_usd_per_mtok`, `label`, `source`; `CHECKED_ON = "2026-09-16"`; `cost(model_id, input_tokens, output_tokens) -> float` rounded to 6 decimals; unknown model raises `KeyError`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_pricing.py
from weather_agent import pricing

def test_cost_uses_both_directions():
    assert pricing.cost("claude-sonnet-5", 1_000_000, 100_000) == 3.0

def test_all_four_models_are_priced():
    assert set(pricing.PRICES) == {"mistral-small-latest", "mistral-medium-latest", "claude-haiku-4-5", "claude-sonnet-5"}
```

```python
# tests/test_trace.py
from weather_agent import trace

def test_finish_sums_steps_and_counts_model_calls():
    t = trace.new_trace("q", "client", {})
    t.add_step(trace.Step("understand", "model", "m", trace.now_iso(), latency_ms=100, input_tokens=10, output_tokens=5, cost_usd=0.001))
    t.add_step(trace.Step("geocode", "service", "open-meteo-geocoding", trace.now_iso(), latency_ms=50))
    t.finish()
    assert t.totals.latency_ms == 150 and t.totals.model_calls == 1 and t.totals.input_tokens == 10

def test_store_keeps_latest_and_lookup():
    store = trace.TraceStore(keep=2)
    a, b, c = (trace.new_trace(q, "c", {}) for q in "abc")
    for t in (a, b, c): store.add(t)
    assert store.latest() is c and store.get(a.id) is None and store.get(b.id) is b

def test_guardrail_event_is_recorded():
    t = trace.new_trace("q", "c", {})
    t.add_guardrail("input_length", "before", "pass", "12 chars")
    assert t.guardrails[0].rule == "input_length"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_trace.py tests/test_pricing.py -q`

- [ ] **Step 3: Implement** both modules as specified. `PRICES` values: mistral-small-latest 0.15 and 0.60, mistral-medium-latest 1.50 and 7.50, claude-haiku-4-5 1.00 and 5.00, claude-sonnet-5 2.00 and 10.00, sources `https://mistral.ai/pricing/api` and `https://platform.claude.com/docs/en/about-claude/pricing`.

- [ ] **Step 4: Run tests to verify they pass**, then commit.

```bash
git add weather_agent/trace.py weather_agent/pricing.py tests/test_trace.py tests/test_pricing.py
git commit -m "Add trace dataclasses, trace store and price table"
```

### Task 7: Providers

**Files:**
- Create: `weather_agent/providers/__init__.py`, `weather_agent/providers/mistral.py`, `weather_agent/providers/anthropic.py`, `tests/test_providers.py`
- Modify: `weather_agent/config.py` to take `MODEL_IDS` from `providers.MODELS`.

**Interfaces:**
- Produces in `providers/__init__.py`:
  - `@dataclass Model: id: str; provider: str; label: str; extras: dict`
  - `MODELS: dict[str, Model]` for the four ids; `claude-sonnet-5` has `extras={"output_config": {"effort": "low"}}`.
  - `@dataclass ToolCall: id: str; name: str; arguments: dict`
  - `@dataclass ModelResponse: text: str; tool_calls: list[ToolCall]; input_tokens: int; output_tokens: int; latency_ms: int; request: dict; raw: dict; stop_reason: str`
  - `class ProviderError(Exception)` with `.status: int` and `.body: str`.
  - `class CallBudget: limit: int = 4; used: int = 0; spend() raises BudgetExceeded when used == limit before incrementing`.
  - `class BudgetExceeded(Exception)`.
  - `call_model(model_id: str, system: str, user_text: str, tools: list[dict] | None, budget: CallBudget, offline: bool, client: httpx.Client, env: dict) -> tuple[ModelResponse, str]` returning the response and the source. Builds the request via the provider module, records with `recording.fetch("model", canonical, live, offline)` where canonical is `{"provider", "url", "body"}` without headers, then parses.
- Produces in each provider module: `build_request(model: Model, system: str, user_text: str, tools: list[dict] | None, api_key: str) -> tuple[str, dict, dict]` as url, headers, body; `parse_response(raw: dict) -> tuple[str, list[ToolCall], int, int, str]` as text, tool calls, input tokens, output tokens, stop reason.
- Mistral body: `{"model", "messages": [{"role": "system", "content": system}, {"role": "user", "content": user_text}], "max_tokens": 1024}` plus `"tools": [{"type": "function", "function": {"name", "description", "parameters": input_schema}}]` and `"tool_choice": "auto"` when tools are given. `arguments` may be a JSON string or an object.
- Anthropic body: `{"model", "max_tokens": 1024, "system": system, "messages": [{"role": "user", "content": user_text}]}` plus `"tools"` with `input_schema` and `"tool_choice": {"type": "auto"}` when tools are given, plus `model.extras`. Headers `x-api-key`, `anthropic-version: 2023-06-01`, `content-type: application/json`. Blocks of type `thinking` are ignored.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_providers.py
import json, httpx, pytest
from weather_agent import providers
from weather_agent.providers import mistral, anthropic

TOOL = {"name": "lookup_place", "description": "d", "input_schema": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}}
ENV = {"MISTRAL_API_KEY": "m", "ANTHROPIC_API_KEY": "a"}

def test_mistral_request_shape():
    url, headers, body = mistral.build_request(providers.MODELS["mistral-small-latest"], "sys", "hi", [TOOL], "key")
    assert url.endswith("/v1/chat/completions") and headers["Authorization"] == "Bearer key"
    assert body["messages"][0] == {"role": "system", "content": "sys"} and body["tools"][0]["function"]["parameters"] == TOOL["input_schema"]

def test_mistral_parse_handles_string_arguments():
    raw = {"choices": [{"message": {"content": None, "tool_calls": [{"id": "abc123def", "function": {"name": "lookup_place", "arguments": "{\"name\": \"Paris\"}"}}]}, "finish_reason": "tool_calls"}], "usage": {"prompt_tokens": 10, "completion_tokens": 4}}
    text, calls, i, o, stop = mistral.parse_response(raw)
    assert calls[0].arguments == {"name": "Paris"} and (i, o, stop) == (10, 4, "tool_calls") and text == ""

def test_anthropic_request_shape_and_extras():
    url, headers, body = anthropic.build_request(providers.MODELS["claude-sonnet-5"], "sys", "hi", [TOOL], "key")
    assert headers["x-api-key"] == "key" and headers["anthropic-version"] == "2023-06-01"
    assert body["system"] == "sys" and body["tools"][0]["input_schema"] == TOOL["input_schema"] and body["output_config"] == {"effort": "low"}
    assert "temperature" not in body

def test_anthropic_parse_ignores_thinking_blocks():
    raw = {"content": [{"type": "thinking", "thinking": ""}, {"type": "text", "text": "ok"}, {"type": "tool_use", "id": "t1", "name": "lookup_place", "input": {"name": "Paris"}}], "stop_reason": "tool_use", "usage": {"input_tokens": 7, "output_tokens": 3}}
    text, calls, i, o, stop = anthropic.parse_response(raw)
    assert text == "ok" and calls[0].name == "lookup_place" and (i, o, stop) == (7, 3, "tool_use")

def test_call_model_records_cost_free_request_without_headers(tmp_path, monkeypatch):
    def handler(request):
        return httpx.Response(200, json={"content": [{"type": "text", "text": "hi"}], "stop_reason": "end_turn", "usage": {"input_tokens": 1, "output_tokens": 1}})
    client = httpx.Client(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(providers.recording, "FIXTURES", tmp_path)
    response, source = providers.call_model("claude-haiku-4-5", "s", "u", None, providers.CallBudget(), False, client, ENV)
    assert response.text == "hi" and source == "live" and "headers" not in response.request
    recorded = json.loads(next((tmp_path / "model").iterdir()).read_text())
    assert "x-api-key" not in json.dumps(recorded)

def test_budget_blocks_fifth_call():
    b = providers.CallBudget()
    for _ in range(4): b.spend()
    with pytest.raises(providers.BudgetExceeded): b.spend()

def test_non_2xx_raises_provider_error():
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(401, text="bad key")))
    with pytest.raises(providers.ProviderError) as e:
        providers.call_model("mistral-small-latest", "s", "u", None, providers.CallBudget(), False, client, ENV)
    assert e.value.status == 401
```

- [ ] **Step 2: Run tests to verify they fail**, implement the three modules, run again until 7 pass. Missing API key raises `ProviderError(status=0, body="MISTRAL_API_KEY is not set")`.

- [ ] **Step 3: Update `config.py`** so `OPTIONS["understand"]` and `["answer"]` come from `list(providers.MODELS)`. Run the whole suite.

- [ ] **Step 4: Commit**

```bash
git add weather_agent/providers weather_agent/config.py tests/test_providers.py
git commit -m "Add Mistral and Anthropic REST clients behind one call_model"
```

### Task 8: Understand

**Files:**
- Create: `weather_agent/understand.py`, `tests/test_understand.py`

**Interfaces:**
- Consumes: `providers.call_model`, `providers.ToolCall`, `forecast.When`.
- Produces: `SYSTEM_PROMPT: str`; `TOOLS: list[dict]` exactly as spec 4.1; `@dataclass Understanding: place: dict | None; when: When | None; notes: list[str]; unknown_tools: list[str]; raw_calls: list[ToolCall]`; `interpret(calls: list[ToolCall]) -> Understanding` implementing the code rules of spec 4.1 including argument validation; `understand(question, model_id, budget, offline, client, env) -> tuple[ModelResponse, Understanding, str]`.
- Validation errors in arguments append to `notes` and drop the field: bad enum values, `days` outside 1 to 15, an unparseable date.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_understand.py
from weather_agent import understand
from weather_agent.providers import ToolCall

def call(name, **args): return ToolCall("id", name, args)

def test_both_tools_give_place_and_when():
    u = understand.interpret([call("lookup_place", name="Paris"), call("get_forecast", when="tomorrow", aspects=["precipitation"])])
    assert u.place == {"name": "Paris", "region": None, "country": None} and u.when.kind == "tomorrow"

def test_lookup_only_defaults_to_now_general():
    u = understand.interpret([call("lookup_place", name="Paris", region="Texas")])
    assert u.when.kind == "now" and u.when.aspects == ["general"] and any("default" in n for n in u.notes)

def test_no_tools_means_no_place():
    u = understand.interpret([])
    assert u.place is None and u.when is None

def test_unknown_tool_is_reported_not_used():
    u = understand.interpret([call("delete_everything", x=1)])
    assert u.unknown_tools == ["delete_everything"] and u.place is None

def test_bad_days_is_dropped_with_note():
    u = understand.interpret([call("lookup_place", name="Oslo"), call("get_forecast", when="period", days=99, aspects=["snow"])])
    assert u.when.days is None and u.notes

def test_system_prompt_forbids_computing_dates():
    assert "never" in understand.SYSTEM_PROMPT.lower() and "date" in understand.SYSTEM_PROMPT.lower()
```

- [ ] **Step 2: Run, implement, run.** `SYSTEM_PROMPT` final text:

```
You are the understanding step of a weather app. You never answer the question yourself.
For a weather question: call lookup_place with the place exactly as the user wrote it, and call get_forecast with when and aspects.
Copy weekday names and dates as the user wrote them. Never compute or convert a date. Never estimate coordinates.
If the message is not a question about the weather at a place, call no tool and reply with the single word NONE.
```

- [ ] **Step 3: Commit**

```bash
git add weather_agent/understand.py tests/test_understand.py
git commit -m "Add the understand step with tool schemas and validation"
```

### Task 9: Answer

**Files:**
- Create: `weather_agent/answer.py`, `tests/test_answer.py`

**Interfaces:**
- Produces: `SYSTEM_PROMPT: str`; `phrase(question: str, facts: dict, model_id, budget, offline, client, env) -> tuple[ModelResponse, str]` where the user text is `f"Question: {question}\nFacts: {json.dumps(facts, ensure_ascii=False)}"`; `template(outcome: str, **kwargs) -> str` with the table from spec 4.4; `suggestions(candidates: list[Candidate]) -> list[str]`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_answer.py
from weather_agent import answer
from weather_agent.geocode import Candidate

def test_templates_cover_every_outcome():
    for outcome in ["not_weather", "no_place", "input_too_long", "rate_limited", "blocked"]:
        assert answer.template(outcome)

def test_not_found_and_out_of_range_use_arguments():
    assert "Qwxlorbia" in answer.template("place_not_found", name="Qwxlorbia")
    assert "1950-01" in answer.template("date_out_of_range", date="1950-01")

def test_ambiguous_lists_three_with_region():
    cands = [Candidate("Springfield", s, "United States", "US", 0, 0, "UTC", 1, "PPL") for s in ["Missouri", "Massachusetts", "Illinois"]]
    text = answer.template("place_ambiguous", name="Springfield", candidates=cands)
    assert "Missouri" in text and "Illinois" in text
    assert answer.suggestions(cands) == ["Weather in Springfield, Missouri, US", "Weather in Springfield, Massachusetts, US", "Weather in Springfield, Illinois, US"]

def test_system_prompt_rules():
    p = answer.SYSTEM_PROMPT.lower()
    assert "two sentences" in p and "language" in p and "only" in p
```

- [ ] **Step 2: Run, implement, run.** `SYSTEM_PROMPT` final text:

```
You phrase weather facts for the user. Use only the values in the facts; add no other knowledge and no advice beyond the verdicts.
At most two sentences, the key number first, with its unit exactly as given. When a verdict is present, start with yes, no or unlikely.
Answer in the language of the question. Name the place, and name the date when the question is about a day other than now.
```

- [ ] **Step 3: Commit**

```bash
git add weather_agent/answer.py tests/test_answer.py
git commit -m "Add the answer step with phrasing prompt and outcome templates"
```

### Task 10: Guardrails

**Files:**
- Create: `weather_agent/guardrails.py`, `tests/test_guardrails.py`

**Interfaces:**
- Produces: `MAX_INPUT_CHARS = 500`; `RATE_LIMIT = 60`; `RATE_WINDOW_S = 60`; `TOLERANCE = 0.5`; `MIN_SENTENCE_CHARS = 30`.
  - `check_length(question: str) -> tuple[bool, str]` as ok and detail.
  - `class RateLimiter: allow(client_id: str, now: float | None = None) -> tuple[bool, str]` with a sliding window in a `dict[str, deque[float]]`. Module-level `LIMITER = RateLimiter()`.
  - `allowed_numbers(facts: dict) -> set[float]`: every int or float in the facts recursively (bools excluded), plus day, month and year of each date in `facts["when"]["dates"]` and of `facts["today"]`, each hour in `facts["when"]["hours"]`, and `len(facts["when"]["dates"])`.
  - `numbers_in(text: str) -> list[float]`: replace `(\d{1,2}):(\d{2})` with the hour, then match `-?\d+(?:[.,]\d+)?`, decimal comma accepted.
  - `check_grounding(answer: str, facts: dict) -> tuple[bool, str]`: every number within `TOLERANCE` of an allowed value; detail names the offending numbers.
  - `check_leak(answer: str, system_prompts: list[str]) -> tuple[bool, str]`: normalise by lowercasing and collapsing whitespace; split prompts on `.`, `!`, `?` and newlines; any sentence of at least `MIN_SENTENCE_CHARS` found in the answer fails.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_guardrails.py
from weather_agent import guardrails as g

FACTS = {"today": "2026-09-16", "when": {"dates": ["2026-09-19"], "hours": [12, 13, 14, 15, 16, 17, 18]},
         "daily": [{"temperature_2m_max": 24.6, "temperature_2m_min": 17.2, "precipitation_probability_max": 35}],
         "verdicts": {"rain": "unlikely", "rain_probability_max": 35, "windy": False}}

def test_length_cap():
    assert g.check_length("a" * 500)[0] and not g.check_length("a" * 501)[0]

def test_rate_limiter_sliding_window():
    limiter = g.RateLimiter()
    assert all(limiter.allow("c", now=100.0 + i)[0] for i in range(60))
    assert not limiter.allow("c", now=159.0)[0]
    assert limiter.allow("c", now=161.0)[0]

def test_numbers_in_handles_decimal_comma_negative_and_times():
    assert g.numbers_in("It is -3,5 °C at 12:00, 35% chance") == [-3.5, 12, 35]

def test_grounding_accepts_rounded_values_and_dates():
    ok, _ = g.check_grounding("Saturday 19 September: 25 °C max and 17 °C min, 35% rain between 12:00 and 18:00.", FACTS)
    assert ok

def test_grounding_rejects_invented_number():
    ok, detail = g.check_grounding("Around 40% chance of rain.", FACTS)
    assert not ok and "40" in detail

def test_leak_detects_a_prompt_sentence_and_ignores_short_ones():
    prompt = "You never answer the question yourself. Be nice."
    assert not g.check_leak("Sure: you never answer the question yourself.", [prompt])[0]
    assert g.check_leak("Be nice.", [prompt])[0]
```

- [ ] **Step 2: Run, implement, run** until 6 pass.

- [ ] **Step 3: Commit**

```bash
git add weather_agent/guardrails.py tests/test_guardrails.py
git commit -m "Add guardrails: length, rate limit, grounding, prompt leak"
```

### Task 11: Pipeline, command line and /api/ask

**Files:**
- Create: `weather_agent/pipeline.py`, `weather_agent/__main__.py`, `tests/test_pipeline.py`
- Modify: `weather_agent/main.py` adding `POST /api/ask`

**Interfaces:**
- Consumes everything above.
- Produces: `run(question: str, settings: Settings, client_id: str, client: httpx.Client | None = None, env: dict | None = None) -> Trace`. Stores the trace in `trace.STORE`. `Trace.outcome` is one of `weather`, `not_weather`, `no_place`, `place_not_found`, `place_ambiguous`, `date_out_of_range`, `input_too_long`, `rate_limited`, `blocked`, `upstream_error`.
- Step order and trace: guardrail events for `input_length` and `rate_limit`; Step `understand` (kind model, handler model id, request body, raw response, result `{"tool_calls": [...], "notes": [...]}`, tokens, cost, source); guardrail `registered_tools` pass or fail; Step `geocode` (kind service, handler `open-meteo-geocoding`, request, raw response, result `{"outcome", "place", "candidates"}`); Step `forecast` with result `{"when": resolved, "facts": facts}` or source `skipped` when the pre-check rejects; Step `answer` with the phrasing call or source `skipped` with result `{"template": outcome}`; guardrails `model_call_budget` (pass with count), `grounding`, `system_prompt_leak`. Exceptions: `ProviderError`, `httpx.HTTPError`, `recording.NoRecording`, `BudgetExceeded` become `upstream_error` with `error` the template and `error_detail` the repr.
- `__main__.py`: `python -m weather_agent ask "question" [--offline]` prints the answer, then one line per step with handler, source, latency, tokens and cost, then guardrail events, then totals.
- `POST /api/ask`: body `{"question": str}`; `client_id` is `request.client.host`; returns `{ok, answer, suggestions, notice, outcome, trace_id, latency_ms, cost_usd, error}` where `ok` is false only for `upstream_error` and `blocked`.

- [ ] **Step 1: Write the failing tests** using `httpx.MockTransport` that routes by host: `geocoding-api.open-meteo.com` returns `tests/fixtures/geocode_paris.json`, `api.open-meteo.com` returns `forecast_paris_now.json`, `api.mistral.ai` returns a canned tool-call response for the first call and a canned text answer for the second.

```python
# tests/test_pipeline.py
import json
from pathlib import Path
import httpx
from weather_agent import pipeline, config, trace

FIX = Path(__file__).parent / "fixtures"
ENV = {"MISTRAL_API_KEY": "m", "ANTHROPIC_API_KEY": "a"}

def mistral_tool_response():
    calls = [{"id": "aaaaaaaaa", "function": {"name": "lookup_place", "arguments": json.dumps({"name": "Paris"})}},
             {"id": "bbbbbbbbb", "function": {"name": "get_forecast", "arguments": json.dumps({"when": "now", "aspects": ["temperature"]})}}]
    return {"choices": [{"message": {"content": None, "tool_calls": calls}, "finish_reason": "tool_calls"}], "usage": {"prompt_tokens": 300, "completion_tokens": 40}}

def mistral_text_response(text):
    return {"choices": [{"message": {"content": text, "tool_calls": None}, "finish_reason": "stop"}], "usage": {"prompt_tokens": 500, "completion_tokens": 20}}

def make_client(answer_text, tool_response=None):
    state = {"model_calls": 0}
    def handler(request):
        host = request.url.host
        if host == "geocoding-api.open-meteo.com":
            return httpx.Response(200, json=json.loads((FIX / "geocode_paris.json").read_text()))
        if host == "api.open-meteo.com":
            return httpx.Response(200, json=json.loads((FIX / "forecast_paris_now.json").read_text()))
        state["model_calls"] += 1
        body = (tool_response or mistral_tool_response()) if state["model_calls"] == 1 else mistral_text_response(answer_text)
        return httpx.Response(200, json=body)
    return httpx.Client(transport=httpx.MockTransport(handler)), state

def settings(): return config.DEFAULT_SETTINGS

def temp(facts_trace):
    return facts_trace.steps[2].result["facts"]["current"]["temperature_2m"]

def test_weather_path_grounded(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline.recording, "FIXTURES", tmp_path)
    client, _ = make_client("PLACEHOLDER")
    # first run to learn the fixture temperature, then answer with it
    t = pipeline.run("Hey, how cold is it in Paris?", settings(), "test", client=client, env=ENV)
    value = temp(t)
    client, _ = make_client(f"It is {round(value)} °C in Paris right now.")
    t = pipeline.run("Hey, how cold is it in Paris?", settings(), "test", client=client, env=ENV)
    assert t.outcome == "weather" and "°C" in t.answer and t.notice == ""
    assert [s.name for s in t.steps] == ["understand", "geocode", "forecast", "answer"]
    assert t.totals.model_calls == 2 and t.totals.cost_usd > 0
    assert {g.rule for g in t.guardrails} >= {"input_length", "rate_limit", "registered_tools", "model_call_budget", "grounding", "system_prompt_leak"}

def test_ungrounded_answer_gets_notice(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline.recording, "FIXTURES", tmp_path)
    client, _ = make_client("It is 99 °C in Paris.")
    t = pipeline.run("How warm is it in Paris?", settings(), "test", client=client, env=ENV)
    assert t.answer.endswith("I could not verify this result.") and any(g.rule == "grounding" and g.outcome == "fail" for g in t.guardrails)

def test_too_long_makes_no_model_call(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline.recording, "FIXTURES", tmp_path)
    client, state = make_client("x")
    t = pipeline.run("w" * 501, settings(), "test", client=client, env=ENV)
    assert t.outcome == "input_too_long" and state["model_calls"] == 0 and t.steps == []

def test_no_tools_is_not_weather(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline.recording, "FIXTURES", tmp_path)
    client, state = make_client("x", tool_response=mistral_text_response("NONE"))
    t = pipeline.run("Tell me a joke.", settings(), "test", client=client, env=ENV)
    assert t.outcome == "not_weather" and state["model_calls"] == 1 and "weather" in t.answer

def test_upstream_error_is_friendly_with_detail(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline.recording, "FIXTURES", tmp_path)
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(500, text="boom")))
    t = pipeline.run("How warm is it in Paris?", settings(), "test", client=client, env=ENV)
    assert t.outcome == "upstream_error" and "boom" in t.error_detail and t.error
```

- [ ] **Step 2: Run, implement `pipeline.py`, run** until 5 pass. Keep `run` under 40 lines by delegating to `_understand_step`, `_geocode_step`, `_forecast_step`, `_answer_step`, `_after_guardrails`, each taking the trace and returning the outcome or data.

- [ ] **Step 3: Add `__main__.py` and `POST /api/ask`**, with an API test:

```python
# append to tests/test_main.py
def test_ask_rejects_long_input_with_ok_body():
    client = TestClient(app)
    body = client.post("/api/ask", json={"question": "x" * 600}).json()
    assert body["ok"] is True and body["outcome"] == "input_too_long" and body["trace_id"]
```

- [ ] **Step 4: Live check of the two assignment questions**

Run: `.venv/bin/python -m weather_agent ask "Hey, how cold is it in Paris?"` and `.venv/bin/python -m weather_agent ask "Will it rain in New York tomorrow?"`
Expected: a two-sentence answer with °C, then yes, no or unlikely with a percentage; each step listed with tokens and cost; the recordings appear under `fixtures/`.

- [ ] **Step 5: Commit and tag**

```bash
git add weather_agent tests fixtures
git commit -m "Add the pipeline, command line and /api/ask"
sed -i 's/VERSION = "0.2.0"/VERSION = "0.3.0"/' weather_agent/__init__.py
git commit -am "Release 0.3.0" && git tag v0.3.0
```

---

## Phase 3: UI (v0.4.0)

### Task 12: Settings, trace, cost and health routes

**Files:**
- Create: `weather_agent/health.py`
- Modify: `weather_agent/main.py`, `tests/test_main.py`

**Interfaces:**
- `GET /api/settings` returns `{"understand", "geocode", "forecast", "answer", "offline", "options": OPTIONS}`; `PUT /api/settings` accepts a subset and returns the same shape; 400 with `{"error"}` on `ValueError`.
- `GET /api/trace` returns the latest trace dict or 404 `{"error": "No request yet."}`; `GET /api/trace/{id}`.
- `GET /api/cost` returns `{"prices": [{"model", "label", "input_usd_per_mtok", "output_usd_per_mtok", "source"}], "checked_on", "last_request": {"trace_id", "cost_usd", "steps": [{"name", "handler", "cost_usd", "input_tokens", "output_tokens"}]} | null, "session_total_usd", "last_eval": null}`.
- `health.check_all(env, client, offline) -> dict` runs six checks in a `ThreadPoolExecutor`: `mistral_key`, `anthropic_key`, `mistral_api` (`GET https://api.mistral.ai/v1/models`), `anthropic_api` (`GET https://api.anthropic.com/v1/models`), `open_meteo_geocoding` (search Paris count 1), `open_meteo_forecast` (Paris current temperature), plus `recordings` with the count as detail and ok true. Timeout 5 s each. Status per spec 8. Cached 60 s in a module variable. `GET /api/health` returns `{"status", "version", "checked_at", "offline", "checks"}`.

- [ ] **Step 1: Write the failing tests** for settings round trip, 400 on bad handler, trace 404 before any request, cost prices count 4, health with a `MockTransport` that answers 200 to everything giving status `ok` and 7 checks.

- [ ] **Step 2: Run, implement, run.** Use `app.state.client = httpx.Client(timeout=15)` created at startup and overridable in tests.

- [ ] **Step 3: Commit**

```bash
git add weather_agent/health.py weather_agent/main.py tests/test_main.py
git commit -m "Add settings, trace, cost and health routes"
```

### Task 13: Ask flow in the browser

**Files:**
- Create: `static/api.js`, `static/app.js`

**Interfaces:**
- `api.js` exports `ask(question)`, `getSettings()`, `putSettings(changes)`, `getTrace()`, `getHealth()`, `getCost()`, `getEval()`, `runEval(model)`, each `fetch` with JSON and throwing `Error(body.error || response.statusText)` on non-2xx.
- `app.js`: on submit, hide the empty state, show the spinner in `#result`, call `ask`, render the answer in `#answer`, the meta line in `#meta` as "model · 640 ms · $0.0012 · Open trace" with the replay notice when `notice` is set, chips in `#suggestions` that set the input value and submit, the error box on `ok: false` or on a thrown error. The two empty-state buttons fill the input and submit. Sets `#version` from `getHealth()`. Ignores a submit while a request is in flight; the input stays enabled.

- [ ] **Step 1: Implement** and check in the browser with the two assignment questions, "Weather in Springfield?" for the chips, and a 600-character paste for the friendly sentence.

- [ ] **Step 2: Commit**

```bash
git add static/api.js static/app.js
git commit -m "Add the ask flow with answer, meta line, chips and errors"
```

### Task 14: Settings modal and pages

**Files:**
- Create: `static/settings.js`, `static/pages/models.js`, `static/pages/trace.js`, `static/pages/eval.js`, `static/pages/cost.js`, `static/pages/static.js`

**Interfaces:**
- `settings.js` exports `openSettings(page = "models")` and `closeSettings()`; wires the gear, the close button, Escape, backdrop click, and the menu buttons; each page module exports `render(container)`.
- `models.js`: four `<select class="select">` from `getSettings().options`, labelled "1 Understand", "2 Geocode", "3 Forecast", "4 Answer", saving on change with `putSettings`, plus an offline checkbox styled as a switch.
- `trace.js`: totals line, guardrails table, one `.card` per step with a header line (name, handler, source badge, latency, tokens, cost) and three `<details>` blocks titled Request, Raw response, Result with `<pre class="code">` JSON. Empty state when 404.
- `cost.js`: price table, last request table, session total, last eval.
- `eval.js`: table and buttons per spec 9; polls `getEval()` every 2 s while `running`; failures list.
- `static.js`: `render(container, title)` with the heading and the muted line "Filled in after the eval results are in."

- [ ] **Step 1: Implement**, open every page in the browser, resize to 1024 to check the modal still fits.

- [ ] **Step 2: Commit**

```bash
git add static/settings.js static/pages
git commit -m "Add the settings modal with models, trace, eval, cost and placeholder pages"
```

### Task 15: Health dot and card

**Files:**
- Modify: `static/app.js`

- [ ] **Step 1: Implement** `refreshHealth()` on load and every 60 s: set the dot class from `status`, fill `#health-card` with one row per check (name, badge ok or fail, latency, detail), toggle the card on click, close on outside click.

- [ ] **Step 2: Check** by removing network: the dot turns amber or red and the card names the failing checks.

- [ ] **Step 3: Commit and tag**

```bash
git add static/app.js
git commit -m "Add the health dot with a details card"
sed -i 's/VERSION = "0.3.0"/VERSION = "0.4.0"/' weather_agent/__init__.py
git commit -am "Release 0.4.0" && git tag v0.4.0
```

---

## Phase 4: eval (v0.5.0)

### Task 16: Golden set and checks

**Files:**
- Create: `weather_agent/eval/__init__.py`, `weather_agent/eval/golden.py`, `weather_agent/eval/checks.py`, `tests/test_eval_checks.py`

**Interfaces:**
- `golden.py`: `@dataclass GoldenItem: id: int; question: str; expected_tools: list[list[str]]; expected_outcome: str; country_code: str | None = None; admin1_contains: str | None = None; expected_when: list[str] | None = None; expected_block: str | None = None; city_centre: tuple[float, float] | None = None; no_forecast_call: bool = False; rules: list[str] = field(default_factory=list)`; `GOLDEN: list[GoldenItem]` with the fifteen items of spec section 10; item 15's question is `"What is the weather in Paris? " * 67` trimmed to 2000 characters.
- `checks.py`:
  - `@dataclass LayerResult: layer: str; applicable: bool; passed: bool; reason: str`
  - `check_tools(item, trace) -> LayerResult`
  - `check_usage(item, trace) -> LayerResult` with `haversine_km(a, b) -> float`, `RADIUS_KM = 50`, date relation via `zoneinfo.ZoneInfo(place timezone)`; expected relations: `now` and `today` need dates empty or `[today]`, `tomorrow` needs `[today + 1]`, `weekday saturday` needs a Saturday within 7 days, `period 7` needs 7 dates starting today; when the forecast step source is `replayed`, today is `facts["today"]` instead of the clock.
  - `check_grounding(item, trace) -> LayerResult`, applicable only for outcome `weather`, passes when the grounding guardrail passed.
  - `check_rules(item, trace) -> LayerResult` running `RULES[name](trace)` for each rule name; `RULES: dict[str, Callable[[Trace], tuple[bool, str]]]` for has_celsius, has_kmh, has_percent, starts_yes_no_unlikely, starts_yes_no, mentions_texas, two_celsius_values, names_the_date, names_days_if_snow, is_dutch, no_system_prompt, max_three_sentences, template_out_of_range, template_not_found, template_which, three_suggestions, template_only_weather, template_too_long.
  - `check_item(item, trace) -> list[LayerResult]` in the order tools, usage, grounding, rules.

- [ ] **Step 1: Write the failing tests** with hand-built traces: a weather trace for item 1 with a Paris place and a grounded answer passes all four layers; a trace with coordinates in Texas fails usage for item 1 with "km" in the reason; item 12 with tools `[]` and outcome `not_weather` passes tools and rules and marks grounding not applicable; `starts_yes_no_unlikely` accepts "Yes, ..." and "Unlikely: ..." and rejects "It will rain"; `is_dutch` accepts "Het is 14 °C in Utrecht." and rejects "It is 14 °C in Utrecht."; `two_celsius_values` needs two numbers followed by °C; `haversine_km` gives about 344 for Paris to London.

- [ ] **Step 2: Run, implement, run.**

- [ ] **Step 3: Commit**

```bash
git add weather_agent/eval tests/test_eval_checks.py
git commit -m "Add the golden set and the four eval layers"
```

### Task 17: Runner, results, API and Eval page

**Files:**
- Create: `weather_agent/eval/runner.py`, `weather_agent/eval/__main__.py`, `weather_agent/eval/results/.gitkeep`, `tests/test_eval_runner.py`
- Modify: `weather_agent/main.py`, `static/pages/eval.js`, `weather_agent/config.py` for `last_eval` in `/api/cost`

**Interfaces:**
- `runner.py`: `run_eval(model_id: str, settings: Settings, client, env, progress: Callable[[int, int], None] | None = None) -> dict` returning `{"run_id", "model", "started_at", "finished_at", "version", "summary": {"tools": {"passed", "applicable"}, "usage": ..., "grounding": ..., "rules": ..., "mean_latency_ms", "mean_cost_usd", "total_cost_usd"}, "items": [{"id", "question", "outcome", "answer", "layers": [LayerResult...], "latency_ms", "cost_usd", "trace": dict}], "failures": [{"item", "layer", "reason"}]}`; `save(result) -> Path` writing `results/<YYYYMMDD-HHMMSS>-<model>.json`; `latest_per_model() -> dict[str, dict]` reading the results directory and keeping only summaries plus failures.
- The runner copies `settings` with `understand` and `answer` set to `model_id`, uses a fresh `RateLimiter` client id per item so the limiter never fires, and calls `pipeline.run` directly.
- `__main__.py`: `python -m weather_agent.eval --model <id|all> [--offline]` prints a table with one row per model and the failures.
- API: `POST /api/eval/run` starts a `threading.Thread` and returns `{"run_id"}`; 409 when a run is in progress. `GET /api/eval` returns `{"running", "progress": {"done", "total"}, "latest": latest_per_model()}`. `GET /api/eval/{run_id}` returns the saved file. `/api/cost.last_eval` becomes `{model: total_cost_usd}` from `latest_per_model()`.

- [ ] **Step 1: Write the failing tests** for `run_eval` with the Task 11 mock client on a two-item subset (monkeypatch `GOLDEN`), asserting summary shapes and that `save` writes a file and `latest_per_model` reads it back.

- [ ] **Step 2: Run, implement, run.**

- [ ] **Step 3: Live run for all four models**

Run: `.venv/bin/python -m weather_agent.eval --model all`
Expected: four rows with pass rates per layer, mean latency and mean cost; failures listed with layer and reason. Then `git status` shows new files under `fixtures/` and `weather_agent/eval/results/`.

- [ ] **Step 4: Replay run**

Run: `.venv/bin/python -m weather_agent.eval --model mistral-medium-latest --offline`
Expected: same pass rates, every step marked replayed, zero network.

- [ ] **Step 5: Commit and tag**

```bash
git add weather_agent static fixtures tests
git commit -m "Add the eval runner, results storage, API and Eval page"
sed -i 's/VERSION = "0.4.0"/VERSION = "0.5.0"/' weather_agent/__init__.py
git commit -am "Release 0.5.0" && git tag v0.5.0
```

---

## Phase 5: review (v0.9.0)

### Task 18: Fresh-eyes review and fixes

- [ ] **Step 1: Dispatch an independent reviewer** with the spec, CLAUDE.md and the repository, asking for anything an interviewer would find unclear, over-engineered or inconsistent with CLAUDE.md, plus correctness bugs, as a list with file and line.
- [ ] **Step 2: Verify each finding** against the code before acting; fix the confirmed ones; list the rejected ones with the reason.
- [ ] **Step 3: Run the full suite and the two assignment questions live.**
- [ ] **Step 4: Commit and tag**

```bash
git commit -am "Review fixes"
sed -i 's/VERSION = "0.5.0"/VERSION = "0.9.0"/' weather_agent/__init__.py
git commit -am "Release 0.9.0" && git tag v0.9.0
```

---

## Phase 6: documents and release (v1.0.0)

### Task 19: Documents

**Files:**
- Create: `README.md`, `docs/ARCHITECTURE.md`, `CHANGELOG.md`
- Modify: `docs/DESIGN.md`, `CLAUDE.md`

- [ ] **Step 1: README**: what it is, screenshot placeholder line, how to run (venv, requirements, .env from .env.example, uvicorn command, URL), how to test, how to run the golden set, offline mode, the four dependencies each with a one-line justification, the usage terms of Open-Meteo with attribution, version and changelog pointer.
- [ ] **Step 2: ARCHITECTURE.md**: Mermaid sequence diagram of one request from input to answer with every model and tool call and every guardrail; Mermaid component diagram marking model steps versus plain code; the rejected-alternatives table from spec section 2 extended with why each was rejected; a section on tracing, recording and the eval layers.
- [ ] **Step 3: DESIGN.md**: replace the settings panel row of the responsive table with the modal: 960 px at 1280, full width minus 48 px at 1024, full screen at 768; add the health dot, the chip and the switch to the component table.
- [ ] **Step 4: CLAUDE.md**: fill "Stack and commands" with the venv, run, test and eval commands; add a "Layout" section listing each module in one line; keep the assignment and principles verbatim.
- [ ] **Step 5: CHANGELOG.md** in Keep a Changelog format with entries 0.1.0 to 1.0.0.
- [ ] **Step 6: Commit, tag, push**

```bash
git add README.md docs CLAUDE.md CHANGELOG.md
git commit -m "Add README, architecture, design and changelog"
sed -i 's/VERSION = "0.9.0"/VERSION = "1.0.0"/' weather_agent/__init__.py
git commit -am "Release 1.0.0" && git tag v1.0.0
git push -u origin main --tags
```

---

## Self-review

- Spec coverage: pipeline stages (Tasks 8 to 11), geocode rule (4), forecast and dates (5), guardrails (10), providers and prices (6, 7), trace (6), recording and offline (3, 11, 12), HTTP API (11, 12, 17), frontend (2, 13, 14, 15), eval (16, 17), cost page (12, 17), versioning and tags (every phase), git and secrets (Task 1 and Global Constraints), documents (19). The health checks and the offline switch are in Tasks 12 and 14.
- Type consistency: `Candidate`, `Selection`, `When`, `Trace`, `Step`, `GuardrailEvent`, `ModelResponse`, `ToolCall`, `CallBudget`, `Understanding`, `LayerResult`, `GoldenItem` are defined once and used by the same names throughout. `recording.fetch` returns `(response, source)` everywhere.
- Deviation from the writing-plans template, stated on purpose: tests are given in full as the contract; implementation steps give signatures, rules and constants rather than full bodies, because the code itself is the deliverable the user will read, and duplicating it here would double the work on a one-day deadline.
