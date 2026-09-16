# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versions follow
[Semantic Versioning](https://semver.org/). One tag per phase.

## [Unreleased]

## [1.1.0] - 2026-09-16

### Added
- Nominatim as a second geocoder, selectable on the Models page: same candidate
  shape, ranked by its importance score, throttled to one request per second,
  with an identifying User-Agent; the forecast asks Open-Meteo for the timezone
  Nominatim lacks. Not the default.
- Model suitability page: the four models compared per layer, latency and cost,
  with an assessment and a recommendation per step from the run of
  16 September 2026.
- EU AI Act page: a working assessment of the app under Regulation (EU)
  2024/1689, with the transparency notice it calls for added to the empty state.
- Eval results for Claude Haiku 4.5 and Claude Sonnet 5, now that the key works.
- An `is_english` eval rule on the English questions, after Claude Sonnet 5
  answered seven of them in German in its first run.

### Changed
- Dark theme in the manner of mistral.ai: their steel neutrals and orange,
  Space Grotesk as the free stand-in for their ALT Mistral headings, Inter for
  text, Space Mono for labels and code, all self-hosted. DESIGN.md rewritten
  with recomputed contrast ratios.
- New pixel mark: a speech bubble of warm squares with three typing dots.
- The answer step puts the facts first and the question last and is told to
  reply in the question's language; every model now answers in English to
  English questions.
- The country filter matches partial names and a few aliases, so "Netherlands"
  finds "The Netherlands"; this had cost Claude Haiku the Utrecht question.
- The settings window has a fixed height, so a loading page no longer makes
  it shrink and flash.
- Failures under the Eval table show five rows and scroll for the rest.
- The Models page text names the four models and both geocoders.

### Removed
- The line under the answer with model, latency, cost and the trace link; the
  Trace page has all of it.
- The data credits line in the footer; the credits are on the Cost page and in
  the README.

## [1.0.0] - 2026-09-16

First complete version for the interview demo.

### Added
- README with run, test and eval instructions and a screenshot; ARCHITECTURE.md
  with the request sequence, the component view, the rejected alternatives and
  the guardrail, recording and eval sections; DESIGN.md updated for the modal,
  the chips, the switch, the health dot, the logo and the fonts; CLAUDE.md
  expanded with stack, commands and layout.

### Known limitations
- The Anthropic key in the local .env was rejected with HTTP 401 during the
  build, so the two Claude models have no eval results yet. Replace the key and
  run `python -m weather_agent.eval --model all`.
- Rejections are English templates; only weather answers follow the language
  of the question.
- The system prompt leak check matches whole sentences; a paraphrase passes.

## [0.9.0] - 2026-09-16

Review release: an independent review from three lenses with every finding
verified against the code; the confirmed ones are fixed here.

### Changed
- A past or far date, an unreadable date text or a day count beyond the
  forecast now reaches the range check and gets the out-of-range answer,
  instead of being silently rewritten to today or a week.
- "Tonight" means the coming night: the night window uses the next date's
  small hours.
- The place the model named is a dataclass; the geocode outcome uses the same
  words as the trace.
- The request boundary records any failure in the trace instead of a bare
  500; a question without a recording in offline mode has its own outcome.
- The model-call budget event is logged as failed when it fires; the budget
  stays at the four the assignment allows, with the reason in the docstring.
- Grounding ignores coordinates, weather codes and the day flag, and allows
  the asked day count.
- Eval traces no longer push the user's traces out of the store; the eval run
  route takes a lock and returns the queued models.
- Health reports a missing recordings directory as degraded.
- Malformed tool arguments from a model are a provider error, not a crash.
- The trace keeps at most 500 characters of a rejected oversized question.
- Labels live in the provider registry only; timeouts and the output cap are
  named constants; stop reasons appear in the trace.

### Removed
- Fifty stale model recordings made with earlier prompts.

## [0.5.0] - 2026-09-16

### Added
- Eval page: models as columns, layers as rows, a Run button per model and
  Run all, progress while running, failures of the latest runs.

### Added
- Golden set of fifteen questions, four eval layers checked by code, a runner
  that saves reports with traces, a command line and the eval API.
- Recordings of every golden question for offline replay.

### Changed
- Wind verdicts carry the wind speed; the understand prompt asks for both tools
  and treats past dates as dates; the answer prompt asks for the number that
  belongs to a verdict.

## [0.4.0] - 2026-09-16

### Added
- The browser front end as plain ES modules: the ask flow with answer, meta
  line, suggestion chips and error box; the settings modal with the Models,
  Trace, Cost and placeholder pages; the health dot with its card.
- Self-hosted fonts, so the page renders the same offline.

## [0.3.0] - 2026-09-16

### Added
- Mistral and Anthropic REST clients behind one `call_model`, with a model
  call budget and request recording.
- The understand step with two tool schemas and argument validation.
- The answer step with the phrasing prompt and outcome templates.
- Guardrails: input length, rate limit, grounding, system prompt leak.
- The pipeline, the trace store, the price table, the command line and the
  API routes for ask, settings, trace, health and cost.

## [0.2.0] - 2026-09-16

### Added
- Open-Meteo geocoding with the population-based selection rule.
- Open-Meteo forecast with date resolution on local dates, the facts object,
  WMO weather words and rain, wind and snow verdicts.
- Request recording and replay.

## [0.1.0] - 2026-09-16

### Added
- Package skeleton, .env loader, in-memory settings, FastAPI shell.
- Page shell with the design tokens, self-hosted fonts, logo and favicon.
- Design spec and implementation plan.
