# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versions follow
[Semantic Versioning](https://semver.org/). One tag per phase.

## [Unreleased]

## [0.5.0] - 2026-09-16

### Added
- Golden set of fifteen questions, four eval layers checked by code, a runner
  that saves reports with traces, a command line and the eval API.
- Recordings of every golden question for offline replay.

### Changed
- Wind verdicts carry the wind speed; the understand prompt asks for both tools
  and treats past dates as dates; the answer prompt asks for the number that
  belongs to a verdict.

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
