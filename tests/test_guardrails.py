from weather_agent import guardrails as g

FACTS = {
    "today": "2026-09-16",
    "when": {"dates": ["2026-09-19"], "hours": [12, 13, 14, 15, 16, 17, 18]},
    "daily": [{"temperature_2m_max": 24.6, "temperature_2m_min": 17.2, "precipitation_probability_max": 35}],
    "verdicts": {"rain": "unlikely", "rain_probability_max": 35, "windy": False},
}


def test_length_cap():
    assert g.check_length("a" * 500)[0] and not g.check_length("a" * 501)[0]


def test_rate_limiter_sliding_window():
    limiter = g.RateLimiter()
    assert all(limiter.allow("c", now=100.0 + i)[0] for i in range(60))
    assert not limiter.allow("c", now=159.0)[0]
    assert limiter.allow("c", now=161.0)[0]


def test_rate_limiter_is_per_client():
    limiter = g.RateLimiter(limit=1)
    assert limiter.allow("a", now=1.0)[0] and limiter.allow("b", now=1.0)[0] and not limiter.allow("a", now=1.5)[0]


def test_numbers_in_handles_decimal_comma_negative_and_times():
    assert g.numbers_in("It is -3,5 °C at 12:00, 35% chance") == [-3.5, 12, 35]


def test_numbers_in_treats_a_range_dash_as_two_numbers():
    assert g.numbers_in("between 12-18 h") == [12, 18]


def test_grounding_accepts_rounded_values_and_dates():
    ok, _ = g.check_grounding("Saturday 19 September: 25 °C max and 17 °C min, 35% rain between 12:00 and 18:00.", FACTS)
    assert ok


def test_grounding_rejects_invented_number():
    ok, detail = g.check_grounding("Around 40% chance of rain.", FACTS)
    assert not ok and "40" in detail


def test_grounding_allows_the_hour_of_a_timestamp_in_the_facts():
    facts = {"current": {"time": "2026-09-16T10:15", "temperature_2m": 14.1}}
    assert g.check_grounding("At 10:15 it is 14 °C.", facts)[0]


def test_booleans_are_not_numbers():
    assert g.allowed_numbers({"verdicts": {"windy": True}}) == {0.0}


def test_leak_detects_a_prompt_sentence_and_ignores_short_ones():
    prompt = "You never answer the question yourself. Be nice."
    assert not g.check_leak("Sure: you never answer the question yourself.", [prompt])[0]
    assert g.check_leak("Be nice.", [prompt])[0]
