import json

import httpx
from pathlib import Path

from weather_agent import geocode

FIX = Path(__file__).parent / "fixtures"


def load(name): return geocode.parse(json.loads((FIX / name).read_text()))


def test_parse_defaults_missing_population_to_zero():
    cands = geocode.parse({"results": [{"name": "X", "latitude": 1.0, "longitude": 2.0, "country_code": "ZZ", "timezone": "UTC", "feature_code": "PPL"}]})
    assert cands[0].population == 0 and cands[0].admin1 == ""


def test_parse_without_results_key_is_empty():
    assert geocode.parse({"generationtime_ms": 0.1}) == []


def test_paris_is_clear_and_picks_france():
    sel = geocode.choose(load("geocode_paris.json"), "Paris", None, None)
    assert sel.outcome == "place" and sel.place.country_code == "FR"


def test_paris_texas_uses_the_region_filter():
    sel = geocode.choose(load("geocode_paris.json"), "Paris", "Texas", None)
    assert sel.outcome == "place" and sel.place.admin1 == "Texas"


def test_springfield_is_ambiguous_with_three_suggestions():
    sel = geocode.choose(load("geocode_springfield.json"), "Springfield", None, None)
    assert sel.outcome == "place_ambiguous" and len(sel.candidates) == 3
    assert all(c.name.lower() == "springfield" for c in sel.candidates)


def test_empty_results_are_not_found():
    assert geocode.choose(load("geocode_empty.json"), "Qwxlorbia", None, None).outcome == "place_not_found"


def test_region_filter_with_no_match_is_not_found():
    assert geocode.choose(load("geocode_paris.json"), "Paris", "Bavaria", None).outcome == "place_not_found"


def test_country_filter_accepts_code_or_name():
    cands = load("geocode_paris.json")
    assert geocode.choose(cands, "Paris", None, "US").place.country_code == "US"
    assert geocode.choose(cands, "Paris", None, "France").place.country_code == "FR"


def test_non_populated_places_are_dropped():
    cands = [geocode.Candidate("Atlantis", "", "Italy", "IT", 0, 0, "Europe/Rome", 0, "AMUS")]
    assert geocode.choose(cands, "Atlantis", None, None).outcome == "place_not_found"


def test_build_request_shape():
    req = geocode.build_request("Paris")
    assert req["params"] == {"name": "Paris", "count": 10, "language": "en", "format": "json"}


def test_search_parses_live_response_and_records_it(tmp_path, monkeypatch):
    from weather_agent import recording
    import httpx

    # Keep the recording out of the real fixtures directory.
    monkeypatch.setattr(recording, "FIXTURES", tmp_path)
    body = json.loads((FIX / "geocode_paris.json").read_text())

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["name"] == "Paris"
        return httpx.Response(200, json=body)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    request, raw, cands, source = geocode.search("Paris", None, None, offline=False, client=client)
    assert raw == body and source == "live" and request["params"]["name"] == "Paris"
    assert cands[0].name == "Paris" and cands[0].country_code == "FR"
    assert (tmp_path / "geocode").exists()


def test_country_filter_accepts_partial_names_and_aliases():
    cands = [geocode.Candidate("Utrecht", "Utrecht", "The Netherlands", "NL", 52.09, 5.12, "Europe/Amsterdam", 376435, "PPLA"),
             geocode.Candidate("Utrecht", "KwaZulu-Natal", "South Africa", "ZA", -27.66, 30.32, "Africa/Johannesburg", 8486, "PPLA3")]
    assert geocode.choose(cands, "Utrecht", None, "Netherlands").place.country_code == "NL"
    assert geocode.choose(cands, "Utrecht", None, "Holland").place.country_code == "NL"
    assert geocode.choose(cands, "Utrecht", None, "nl").place.country_code == "NL"


def test_short_country_text_never_matches_inside_a_longer_name():
    cands = [geocode.Candidate("Minsk", "", "Belarus", "BY", 53.9, 27.57, "Europe/Minsk", 1, "PPLC")]
    assert geocode.choose(cands, "Minsk", None, "US").outcome == "place_not_found"



def load_nominatim(name):
    return geocode.parse_nominatim(json.loads((FIX / name).read_text()))


def test_nominatim_paris_merges_the_city_and_its_suburb_entry():
    cands = load_nominatim("nominatim_paris.json")
    assert len(cands) == 2 and all(c.timezone == "" for c in cands)
    sel = geocode.choose(cands, "Paris", None, None, "nominatim")
    assert sel.outcome == "place" and sel.place.country_code == "FR" and sel.place.admin1 == "Ile-de-France"


def test_nominatim_springfield_is_ambiguous_by_importance():
    sel = geocode.choose(load_nominatim("nominatim_springfield.json"), "Springfield", None, None, "nominatim")
    assert sel.outcome == "place_ambiguous" and [c.admin1 for c in sel.candidates] == ["Illinois", "Massachusetts", "Missouri"]


def test_nominatim_query_carries_region_and_country_and_names_the_app(tmp_path, monkeypatch):
    from weather_agent import recording

    monkeypatch.setattr(recording, "FIXTURES", tmp_path)
    monkeypatch.setattr(geocode, "NOMINATIM_MIN_INTERVAL_S", 0)
    body = json.loads((FIX / "nominatim_paris_texas.json").read_text())

    def handler(request):
        assert request.url.params["q"] == "Paris, Texas" and request.url.params["format"] == "jsonv2"
        assert request.headers["User-Agent"].startswith("weather-agent/")
        return httpx.Response(200, json=body)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    request, raw, cands, source = geocode.search("Paris", "Texas", None, False, client, "nominatim")
    assert request["url"] == geocode.NOMINATIM_URL and source == "live"
    sel = geocode.choose(cands, "Paris", "Texas", None, "nominatim")
    assert sel.outcome == "place" and sel.place.admin1 == "Texas" and sel.place.population == 25171


def test_nominatim_empty_list_is_not_found():
    assert geocode.choose(load_nominatim("nominatim_qwxlorbia.json"), "Qwxlorbia", None, None, "nominatim").outcome == "place_not_found"
