from weather_agent import answer
from weather_agent.geocode import Candidate


def test_templates_cover_every_outcome():
    for outcome in ["not_weather", "no_place", "input_too_long", "rate_limited", "blocked"]:
        assert answer.template(outcome)


def test_not_found_out_of_range_and_upstream_use_arguments():
    assert "Qwxlorbia" in answer.template("place_not_found", name="Qwxlorbia")
    assert "1950-01" in answer.template("date_out_of_range", date="1950-01")
    assert "forecast" in answer.template("upstream_error", service="forecast")


def test_ambiguous_lists_three_with_region():
    cands = [Candidate("Springfield", s, "United States", "US", 0, 0, "UTC", 1, "PPL") for s in ["Missouri", "Massachusetts", "Illinois"]]
    text = answer.template("place_ambiguous", name="Springfield", candidates=cands)
    assert "Missouri" in text and "Illinois" in text and text.startswith("Which Springfield")
    assert answer.suggestions(cands) == ["Weather in Springfield, Missouri, US", "Weather in Springfield, Massachusetts, US", "Weather in Springfield, Illinois, US"]


def test_place_label_skips_missing_region():
    assert answer.place_label(Candidate("Paris", "", "France", "FR", 0, 0, "UTC", 1, "PPL")) == "Paris, FR"


def test_system_prompt_rules():
    p = answer.SYSTEM_PROMPT.lower()
    assert "two sentences" in p and "language" in p and "only" in p
