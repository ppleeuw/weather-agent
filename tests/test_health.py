import httpx

from weather_agent import health

ENV = {"MISTRAL_API_KEY": "m", "ANTHROPIC_API_KEY": "a"}


def client_answering(status_for):
    return httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(status_for(r.url.host))))


def test_all_green_is_ok_with_seven_checks():
    report = health.check_all(ENV, client_answering(lambda host: 200), offline=False, use_cache=False)
    assert report["status"] == "ok" and len(report["checks"]) == 7 and report["version"]


def test_missing_key_is_degraded():
    report = health.check_all({}, client_answering(lambda host: 200), offline=False, use_cache=False)
    assert report["status"] == "degraded"
    assert not next(c for c in report["checks"] if c["name"] == "mistral_key")["ok"]


def test_open_meteo_down_is_down():
    report = health.check_all(ENV, client_answering(lambda host: 503 if "open-meteo" in host else 200), offline=False, use_cache=False)
    assert report["status"] == "down"


def test_network_error_is_a_failed_check_not_an_exception():
    def handler(request):
        raise httpx.ConnectError("offline")

    report = health.check_all(ENV, httpx.Client(transport=httpx.MockTransport(handler)), offline=True, use_cache=False)
    assert report["status"] == "down" and report["offline"] is True
    assert next(c for c in report["checks"] if c["name"] == "mistral_api")["detail"] == "ConnectError"


def test_cache_returns_the_same_report():
    first = health.check_all(ENV, client_answering(lambda host: 200), offline=False, use_cache=False)
    second = health.check_all({}, client_answering(lambda host: 500), offline=False)
    assert second is first
