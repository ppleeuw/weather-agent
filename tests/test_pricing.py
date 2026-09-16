from weather_agent import pricing


def test_cost_uses_both_directions():
    assert pricing.cost("claude-sonnet-5", 1_000_000, 100_000) == 3.0


def test_all_four_models_are_priced():
    assert set(pricing.PRICES) == {"mistral-small-latest", "mistral-medium-latest", "claude-haiku-4-5", "claude-sonnet-5"}


def test_cost_is_rounded_to_micro_dollars():
    assert pricing.cost("mistral-small-latest", 333, 77) == round(333 / 1e6 * 0.15 + 77 / 1e6 * 0.60, 6)
