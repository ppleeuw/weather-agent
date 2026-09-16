from weather_agent import understand
from weather_agent.providers import ToolCall


def call(tool, **args):
    return ToolCall("id", tool, args)


def test_both_tools_give_place_and_when():
    u = understand.interpret([call("lookup_place", name="Paris"), call("get_forecast", when="tomorrow", aspects=["precipitation"])])
    assert u.place == {"name": "Paris", "region": None, "country": None} and u.when.kind == "tomorrow"
    assert u.when.aspects == ["precipitation"] and u.asked_forecast


def test_lookup_only_defaults_to_now_general():
    u = understand.interpret([call("lookup_place", name="Paris", region="Texas")])
    assert u.when.kind == "now" and u.when.aspects == ["general"] and any("default" in n for n in u.notes)
    assert u.place["region"] == "Texas" and not u.asked_forecast


def test_no_tools_means_no_place():
    u = understand.interpret([])
    assert u.place is None and u.when is None


def test_forecast_without_place_leaves_place_none_but_records_the_call():
    u = understand.interpret([call("get_forecast", when="now", aspects=["general"])])
    assert u.place is None and u.when is None and u.asked_forecast


def test_unknown_tool_is_reported_not_used():
    u = understand.interpret([call("delete_everything", x=1)])
    assert u.unknown_tools == ["delete_everything"] and u.place is None


def test_bad_days_is_dropped_with_note_and_period_defaults_to_seven():
    u = understand.interpret([call("lookup_place", name="Oslo"), call("get_forecast", when="period", days=99, aspects=["snow"])])
    assert u.when.days == 7 and u.notes


def test_weekday_is_lowercased_and_validated():
    u = understand.interpret([call("lookup_place", name="Tokyo"), call("get_forecast", when="weekday", weekday="Saturday", aspects=["temperature"])])
    assert u.when.kind == "weekday" and u.when.weekday == "saturday"


def test_weekday_kind_without_weekday_falls_back_to_today():
    u = understand.interpret([call("lookup_place", name="Tokyo"), call("get_forecast", when="weekday", aspects=["temperature"])])
    assert u.when.kind == "today"


def test_month_precision_date_is_kept_and_bad_date_dropped():
    good = understand.interpret([call("lookup_place", name="Berlin"), call("get_forecast", when="date", date="1950-01", aspects=["temperature"])])
    assert good.when.kind == "date" and good.when.date == "1950-01"
    bad = understand.interpret([call("lookup_place", name="Berlin"), call("get_forecast", when="date", date="January 1950", aspects=["temperature"])])
    assert bad.when.kind == "today" and bad.when.date is None


def test_system_prompt_forbids_computing_dates():
    assert "never" in understand.SYSTEM_PROMPT.lower() and "date" in understand.SYSTEM_PROMPT.lower()


def test_tool_schemas_have_the_two_registered_names():
    assert understand.TOOL_NAMES == {"lookup_place", "get_forecast"}
