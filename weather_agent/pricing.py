"""List prices per million tokens and the cost of one model call.

Why a table in code: the cost of every request is computed from published
list prices, so the Cost page can show exactly where each figure comes from.
Prices were read from the two source pages on CHECKED_ON. Service steps cost
nothing; only model steps have tokens. Model labels live in the provider registry.
"""
from __future__ import annotations

CHECKED_ON = "2026-09-16"

MISTRAL_PRICING = "https://mistral.ai/pricing/api"
ANTHROPIC_PRICING = "https://platform.claude.com/docs/en/about-claude/pricing"

PRICES: dict[str, dict] = {
    "mistral-small-latest": {
        "input_usd_per_mtok": 0.15,
        "output_usd_per_mtok": 0.60,
        "source": MISTRAL_PRICING,
    },
    "mistral-medium-latest": {
        "input_usd_per_mtok": 1.50,
        "output_usd_per_mtok": 7.50,
        "source": MISTRAL_PRICING,
    },
    "claude-haiku-4-5": {
        "input_usd_per_mtok": 1.00,
        "output_usd_per_mtok": 5.00,
        "source": ANTHROPIC_PRICING,
    },
    "claude-sonnet-5": {
        "input_usd_per_mtok": 2.00,
        "output_usd_per_mtok": 10.00,
        "source": ANTHROPIC_PRICING,
    },
}

MILLION = 1_000_000


def cost(model_id: str, input_tokens: int, output_tokens: int) -> float:
    """USD for one call, rounded to a millionth of a dollar."""
    price = PRICES[model_id]
    usd = (
        input_tokens / MILLION * price["input_usd_per_mtok"]
        + output_tokens / MILLION * price["output_usd_per_mtok"]
    )
    return round(usd, 6)
