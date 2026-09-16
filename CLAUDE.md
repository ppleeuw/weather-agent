# Weather Agent

Built for a technical interview on 17 September 2026. Later tools follow the same rules as the first one.

## Assignment (verbatim)

Build an app with a UI/front-end exposing an AI agent that is able to accurately give you the weather when prompted in natural language. For example, the app should accurately answer the following questions: "Hey, how cold is it in Paris?" or "Will it rain in New York tomorrow?".
Useful resources:
- https://open-meteo.com/
- https://nominatim.openstreetmap.org/search

Temperatures are shown in Celsius.

## Principles

- The model only understands the request and phrases the answer. Dates, timezones, units, validation, arithmetic and lookups are code.
- Every request is traceable end to end: prompt, each tool call and its arguments, each raw result, final answer, tokens, latency, cost.
- Every tool has a golden set of questions with expected behaviour and can be run against it.
- Every tool runs without network using cached responses. A demo never depends on wifi.
- Clarity over cleverness. An interviewer will read this code.

## Stack and commands

Python 3.14, FastAPI, uvicorn, httpx, pytest. Frontend: plain HTML, CSS and JavaScript ES modules served by FastAPI, no build step. Both model providers are called over REST with httpx. Forecasts come from Open-Meteo; geocoding from Open-Meteo Geocoding by default or Nominatim when selected.

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env                                   # fill in MISTRAL_API_KEY and ANTHROPIC_API_KEY
.venv/bin/uvicorn weather_agent.main:app --reload      # http://127.0.0.1:8000
.venv/bin/pytest -q                                    # no network
.venv/bin/python -m weather_agent ask "Hey, how cold is it in Paris?" [--offline]
.venv/bin/python -m weather_agent.eval --model all [--offline]
```

## Layout

| Path | What it is |
|---|---|
| `weather_agent/pipeline.py` | one request: guardrails, understand, geocode, forecast, answer, guardrails |
| `weather_agent/understand.py` | step 1, model: system prompt, the two tool schemas, validation of the model's tool calls |
| `weather_agent/geocode.py` | step 2, service: Open-Meteo Geocoding or Nominatim, one candidate shape, the place selection rule |
| `weather_agent/forecast.py`, `verdicts.py` | step 3, service: Open-Meteo Forecast, date resolution on local dates, facts, verdicts |
| `weather_agent/answer.py` | step 4, model: phrasing prompt and the English templates for every other outcome |
| `weather_agent/guardrails.py` | length, rate limit, grounding, system prompt leak |
| `weather_agent/providers/` | registry of the four models, Mistral and Anthropic REST clients, call budget |
| `weather_agent/recording.py` | record every live response, replay offline or on network failure |
| `weather_agent/trace.py`, `pricing.py` | trace dataclasses and store; list prices and cost per call |
| `weather_agent/health.py` | the seven dependency checks behind the dot |
| `weather_agent/main.py`, `config.py` | FastAPI routes; .env loading and in-memory settings |
| `weather_agent/eval/` | golden set, the four layer checks, the runner, saved results |
| `static/` | the page: index.html, styles.css (dark Mistral theme), app.js, settings.js, pages/ (models, trace, eval, cost, suitability, eu-ai-act), fonts/, pixel logo |
| `fixtures/` | recordings of the golden set for offline replay |
| `tests/` | one file per module, fixtures under tests/fixtures |
| `docs/` | ARCHITECTURE.md, DESIGN.md, the spec and the plan under superpowers/ |

Versioning: `VERSION` in `weather_agent/__init__.py`, shown in the footer, in `/api/health` and in every trace; `CHANGELOG.md`; one git tag per phase.

## Project documents

Kept current in the same commit as any behaviour change:

- README: what it is, how to run, tests, golden set.
- docs/ARCHITECTURE.md: Mermaid diagram of one request from input to answer with every model and tool call; a component view marking model vs plain code; a rejected-alternatives table. Exists for every tool so technical questions can be answered from the diagram.
- docs/DESIGN.md: the design system for every tool: tokens, colour rules, type scale, spacing, component styles, responsive behaviour.
- CLAUDE.md: this file, expanded with stack, commands and layout after the first working version.

## Definition of done per phase

Tests pass. Both assignment questions answer correctly. Golden set runs. The three documents are current. One commit.
