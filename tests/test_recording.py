import httpx
import pytest

from weather_agent import recording


def boom():
    raise httpx.ConnectError("no network")


def test_live_call_is_recorded_and_returned(tmp_path):
    response, source = recording.fetch("geocode", {"name": "Paris"}, lambda: {"ok": 1}, offline=False, root=tmp_path)
    assert (response, source) == ({"ok": 1}, "live")
    assert (tmp_path / "geocode" / f"{recording.key_for({'name': 'Paris'})}.json").exists()


def test_offline_replays_recording(tmp_path):
    recording.fetch("geocode", {"name": "Paris"}, lambda: {"ok": 1}, offline=False, root=tmp_path)
    assert recording.fetch("geocode", {"name": "Paris"}, boom, offline=True, root=tmp_path) == ({"ok": 1}, "replayed")


def test_offline_without_recording_raises(tmp_path):
    with pytest.raises(recording.NoRecording):
        recording.fetch("geocode", {"name": "Nowhere"}, boom, offline=True, root=tmp_path)


def test_transport_error_falls_back_to_recording(tmp_path):
    recording.fetch("forecast", {"lat": 1}, lambda: {"t": 2}, offline=False, root=tmp_path)
    assert recording.fetch("forecast", {"lat": 1}, boom, offline=False, root=tmp_path) == ({"t": 2}, "replayed")


def test_transport_error_without_recording_reraises(tmp_path):
    with pytest.raises(httpx.TransportError):
        recording.fetch("forecast", {"lat": 9}, boom, offline=False, root=tmp_path)


def test_key_is_order_independent():
    assert recording.key_for({"a": 1, "b": 2}) == recording.key_for({"b": 2, "a": 1})


def test_count_counts_json_files(tmp_path):
    assert recording.count(tmp_path) == 0
    recording.fetch("geocode", {"name": "Paris"}, lambda: {"ok": 1}, offline=False, root=tmp_path)
    assert recording.count(tmp_path) == 1
