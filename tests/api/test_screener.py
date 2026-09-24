from fastapi.testclient import TestClient

from src.api.main import app


client = TestClient(app)


def test_screener_min_roe_returns_only_qualifying_companies() -> None:
    response = client.get("/api/v1/screener", params={"min_roe": 15})
    assert response.status_code == 200
    assert all(row["return_on_equity_pct"] >= 15 for row in response.json())


def test_screener_rejects_invalid_numeric_parameter() -> None:
    response = client.get("/api/v1/screener", params={"min_roe": "not-a-number"})
    assert response.status_code == 400
