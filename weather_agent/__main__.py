"""Command line: python -m weather_agent ask "question" [--offline]

Prints the answer, then one line per step with handler, source, latency,
tokens and cost, then the guardrail events, then the totals. The same
pipeline the web app uses, without the browser.
"""
from __future__ import annotations

import argparse
from dataclasses import replace

from weather_agent import config, pipeline


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m weather_agent")
    sub = parser.add_subparsers(dest="command", required=True)
    ask = sub.add_parser("ask", help="answer one weather question and show its trace")
    ask.add_argument("question")
    ask.add_argument("--offline", action="store_true", help="replay recordings, make no network calls")
    args = parser.parse_args()
    settings = replace(config.current_settings(), offline=args.offline)
    t = pipeline.run(args.question, settings, client_id="cli")
    print(t.error or t.answer)
    for chip in t.suggestions:
        print(f"  suggestion: {chip}")
    print()
    for step in t.steps:
        tokens = f"{step.input_tokens} in / {step.output_tokens} out" if step.kind == "model" else ""
        print(f"{step.name:<11} {step.handler:<24} {step.source:<9} {step.latency_ms:>6} ms  {tokens:<20} ${step.cost_usd:.6f}  {step.error or ''}")
    for event in t.guardrails:
        print(f"guardrail   {event.rule:<20} {event.stage:<7} {event.outcome:<5} {event.detail}")
    total = t.totals
    print(f"\noutcome {t.outcome} | {total.latency_ms} ms | {total.input_tokens} in / {total.output_tokens} out | ${total.cost_usd:.6f} | {total.model_calls} model calls | trace {t.id}")


if __name__ == "__main__":
    main()
