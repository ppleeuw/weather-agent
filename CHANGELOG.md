# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versions follow
[Semantic Versioning](https://semver.org/). One tag per phase.

## [Unreleased]

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
