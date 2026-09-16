import json
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
    assert sel.outcome == "ambiguous" and len(sel.candidates) == 3
    assert all(c.name.lower() == "springfield" for c in sel.candidates)


def test_empty_results_are_not_found():
    assert geocode.choose(load("geocode_empty.json"), "Qwxlorbia", None, None).outcome == "not_found"


def test_region_filter_with_no_match_is_not_found():
    assert geocode.choose(load("geocode_paris.json"), "Paris", "Bavaria", None).outcome == "not_found"


def test_country_filter_accepts_code_or_name():
    cands = load("geocode_paris.json")
    assert geocode.choose(cands, "Paris", None, "US").place.country_code == "US"
    assert geocode.choose(cands, "Paris", None, "France").place.country_code == "FR"


def test_non_populated_places_are_dropped():
    cands = [geocode.Candidate("Atlantis", "", "Italy", "IT", 0, 0, "Europe/Rome", 0, "AMUS")]
    assert geocode.choose(cands, "Atlantis", None, None).outcome == "not_found"


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
    raw, cands, source = geocode.search("Paris", offline=False, client=client)
    assert raw == body and source == "live"
    assert cands[0].name == "Paris" and cands[0].country_code == "FR"
    assert (tmp_path / "geocode").exists()
