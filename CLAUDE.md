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

Written after the first working version, from the code as built. No language or framework is chosen yet.

## Project documents

Kept current in the same commit as any behaviour change:

- README: what it is, how to run, tests, golden set.
- docs/ARCHITECTURE.md: Mermaid diagram of one request from input to answer with every model and tool call; a component view marking model vs plain code; a rejected-alternatives table. Exists for every tool so technical questions can be answered from the diagram.
- docs/DESIGN.md: the design system for every tool: tokens, colour rules, type scale, spacing, component styles, responsive behaviour.
- CLAUDE.md: this file, expanded with stack, commands and layout after the first working version.

## Definition of done per phase

Tests pass. Both assignment questions answer correctly. Golden set runs. The three documents are current. One commit.
