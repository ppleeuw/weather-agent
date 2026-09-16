from fastapi.testclient import TestClient

from weather_agent import VERSION
from weather_agent.main import app


def test_health_reports_version():
    client = TestClient(app)
    body = client.get("/api/health").json()
    assert body["version"] == VERSION


def test_root_serves_index():
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200 and "<title>" in response.text
