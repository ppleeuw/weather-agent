from weather_agent import trace


def test_finish_sums_steps_and_counts_model_calls():
    t = trace.new_trace("q", "client", {})
    t.add_step(trace.Step("understand", "model", "m", trace.now_iso(), latency_ms=100, input_tokens=10, output_tokens=5, cost_usd=0.001))
    t.add_step(trace.Step("geocode", "service", "open-meteo-geocoding", trace.now_iso(), latency_ms=50))
    t.add_step(trace.Step("answer", "model", "m", trace.now_iso(), source="skipped"))
    t.finish()
    assert t.totals.latency_ms == 150 and t.totals.model_calls == 1 and t.totals.input_tokens == 10


def test_store_keeps_latest_and_lookup():
    store = trace.TraceStore(keep=2)
    a, b, c = (trace.new_trace(q, "c", {}) for q in "abc")
    for t in (a, b, c):
        store.add(t)
    assert store.latest() is c and store.get(a.id) is None and store.get(b.id) is b


def test_store_session_cost_counts_every_trace():
    store = trace.TraceStore(keep=1)
    for _ in range(3):
        t = trace.new_trace("q", "c", {})
        t.add_step(trace.Step("understand", "model", "m", trace.now_iso(), cost_usd=0.5))
        t.finish()
        store.add(t)
    assert store.session_cost() == 1.5


def test_guardrail_event_is_recorded():
    t = trace.new_trace("q", "c", {})
    t.add_guardrail("input_length", "before", "pass", "12 chars")
    assert t.guardrails[0].rule == "input_length" and t.to_dict()["guardrails"][0]["outcome"] == "pass"
