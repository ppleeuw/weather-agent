from weather_agent import understand
from weather_agent.providers import ToolCall
from weather_agent.understand import Place


def call(tool, **args):
    return ToolCall("id", tool, args)


def test_both_tools_give_place_and_when():
    u = understand.interpret([call("lookup_place", name="Paris"), call("get_forecast", when="tomorrow", aspects=["precipitation"])])
    assert u.place == Place("Paris") and u.when.kind == "tomorrow"
    assert u.when.aspects == ["precipitation"] and u.asked_weather


def test_lookup_only_defaults_to_now_general():
    u = understand.interpret([call("lookup_place", name="Paris", region="Texas")])
    assert u.when.kind == "now" and u.when.aspects == ["general"] and any("default" in n for n in u.notes)
    assert u.place.region == "Texas" and u.asked_weather


def test_no_tools_means_no_place():
    u = understand.interpret([])
    assert u.place is None and u.when is None


def test_forecast_without_place_leaves_place_none_but_records_the_call():
    u = understand.interpret([call("get_forecast", when="now", aspects=["general"])])
    assert u.place is None and u.when is None and u.asked_weather


def test_lookup_with_empty_name_still_counts_as_a_weather_question():
    u = understand.interpret([call("lookup_place", name="")])
    assert u.place is None and u.asked_weather and any("no name" in n for n in u.notes)


def test_unknown_tool_is_reported_not_used():
    u = understand.interpret([call("delete_everything", x=1)])
    assert u.unknown_tools == ["delete_everything"] and u.place is None


def test_far_days_are_kept_for_the_range_check_but_nonsense_is_dropped():
    far = understand.interpret([call("lookup_place", name="Oslo"), call("get_forecast", when="period", days=99, aspects=["snow"])])
    assert far.when.days == 99 and not far.notes  # forecast.precheck will reject it with a clear message
    nonsense = understand.interpret([call("lookup_place", name="Oslo"), call("get_forecast", when="period", days="many", aspects=["snow"])])
    assert nonsense.when.days == 7 and nonsense.notes
    flag = understand.interpret([call("lookup_place", name="Oslo"), call("get_forecast", when="in_days", days=True, aspects=["snow"])])
    assert flag.when.kind == "tomorrow" and flag.when.days is None


def test_weekday_is_lowercased_and_validated():
    u = understand.interpret([call("lookup_place", name="Tokyo"), call("get_forecast", when="weekday", weekday="Saturday", aspects=["temperature"])])
    assert u.when.kind == "weekday" and u.when.weekday == "saturday"


def test_weekday_kind_without_weekday_falls_back_to_today():
    u = understand.interpret([call("lookup_place", name="Tokyo"), call("get_forecast", when="weekday", aspects=["temperature"])])
    assert u.when.kind == "today"


def test_date_text_is_kept_as_written_for_the_range_check():
    good = understand.interpret([call("lookup_place", name="Berlin"), call("get_forecast", when="date", date="1950-01", aspects=["temperature"])])
    assert good.when.kind == "date" and good.when.date == "1950-01"
    words = understand.interpret([call("lookup_place", name="Berlin"), call("get_forecast", when="date", date="January 1950", aspects=["temperature"])])
    assert words.when.kind == "date" and words.when.date == "January 1950"


def test_now_with_a_part_of_day_becomes_today():
    u = understand.interpret([call("lookup_place", name="London"), call("get_forecast", when="now", part_of_day="afternoon", aspects=["precipitation"])])
    assert u.when.kind == "today" and u.when.part_of_day == "afternoon" and u.notes


def test_repeated_tool_calls_are_noted():
    u = understand.interpret([call("lookup_place", name="Paris"), call("lookup_place", name="Rome")])
    assert u.place.name == "Rome" and any("called again" in n for n in u.notes)


def test_unknown_aspects_are_noted():
    u = understand.interpret([call("lookup_place", name="Paris"), call("get_forecast", when="now", aspects=["humidity"])])
    assert u.when.aspects == ["general"] and any("humidity" in n for n in u.notes)


def test_system_prompt_forbids_computing_dates():
    assert "never compute or convert a date" in understand.SYSTEM_PROMPT.lower()


def test_tool_schemas_have_the_two_registered_names():
    assert understand.TOOL_NAMES == {"lookup_place", "get_forecast"}
