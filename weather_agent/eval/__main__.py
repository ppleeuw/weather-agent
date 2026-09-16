"""Command line: python -m weather_agent.eval --model <id|all> [--offline]"""
from __future__ import annotations

import argparse
from dataclasses import replace

from weather_agent import config
from weather_agent.eval import runner
from weather_agent.providers import MODELS


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m weather_agent.eval")
    parser.add_argument("--model", default="all", help="a model id from the registry, or all")
    parser.add_argument("--offline", action="store_true", help="replay recordings, make no network calls")
    args = parser.parse_args()
    models = list(MODELS) if args.model == "all" else [args.model]
    settings = replace(config.current_settings(), offline=args.offline)
    results = []
    for model_id in models:
        print(f"running {model_id} ...", flush=True)
        result = runner.run_eval(model_id, settings, progress=lambda done, total: print(f"  {done}/{total}", end="\r", flush=True))
        path = runner.save(result)
        print(f"  saved {path.name}")
        results.append(result)
    print()
    runner.print_report(results)


if __name__ == "__main__":
    main()
