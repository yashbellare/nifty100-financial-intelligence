from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)


def test_health_returns_status_and_all_database_tables() -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert len(body["db_row_counts"]) >= 10
    assert all(isinstance(count, int) for count in body["db_row_counts"].values())
