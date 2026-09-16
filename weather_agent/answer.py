"""Step 4: phrase the facts, or pick a template.

Only weather outcomes reach the model. Every other outcome, such as a place
that was not found or a question that is not about weather, gets a fixed
English sentence from code: cheaper, deterministic, and it never shows a
hostile input to a model a second time.
"""
from __future__ import annotations

import json

import httpx

from weather_agent import providers
from weather_agent.geocode import Candidate
from weather_agent.providers import CallBudget, ModelResponse

SYSTEM_PROMPT = (
    "You phrase weather facts for the user. Use only the values in the facts; add no other "
    "knowledge and no advice beyond the verdicts.\n"
    "At most two sentences, the key number first, with its unit exactly as given. When the "
    "facts contain a verdict, start with yes, no or unlikely.\n"
    "Answer in the language of the question. Name the place, and name the date when the "
    "question is about a day other than now."
)

TEMPLATES = {
    "not_weather": "I can only help with the weather. Ask me about the weather in a place, today or in the coming days.",
    "no_place": "Which place do you mean? Name a city and I will look up the weather.",
    "place_not_found": 'I could not find a place called "{name}". Check the spelling or add a country.',
    "date_out_of_range": "I only cover current conditions and the coming days. {date} is outside that range.",
    "input_too_long": "Your question is longer than 500 characters. Please shorten it.",
    "rate_limited": "Too many requests from this client. Wait a minute and try again.",
    "blocked": "I cannot show that answer.",
    "upstream_error": "The {service} service did not respond. Try again in a moment.",
}


def phrase(
    question: str, facts: dict, model_id: str, budget: CallBudget, offline: bool, client: httpx.Client, env: dict
) -> tuple[ModelResponse, str]:
    """One model call with the question and the facts. Returns (response, source)."""
    user_text = f"Question: {question}\nFacts: {json.dumps(facts, ensure_ascii=False)}"
    return providers.call_model(model_id, SYSTEM_PROMPT, user_text, None, budget, offline, client, env)


def template(outcome: str, **values: object) -> str:
    """The fixed sentence for a non-weather outcome."""
    if outcome == "place_ambiguous":
        return _which(str(values["name"]), values["candidates"])  # type: ignore[arg-type]
    return TEMPLATES[outcome].format(**values)


def suggestions(candidates: list[Candidate]) -> list[str]:
    """Chip texts for an ambiguous place; each is a complete new question."""
    return [f"Weather in {place_label(c)}" for c in candidates[:3]]


def place_label(candidate: Candidate) -> str:
    parts = [candidate.name, candidate.admin1, candidate.country_code]
    return ", ".join(part for part in parts if part)


def _which(name: str, candidates: list[Candidate]) -> str:
    labels = [place_label(c) for c in candidates[:3]]
    if len(labels) > 1:
        listed = ", ".join(labels[:-1]) + " or " + labels[-1]
    else:
        listed = labels[0]
    return f"Which {name} do you mean? {listed}?"
