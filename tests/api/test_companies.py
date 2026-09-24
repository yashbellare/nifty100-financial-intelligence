from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)


def test_companies_list_returns_records():
    response = client.get("/api/v1/companies")
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)
    assert len(payload) >= 1
    assert {"id", "company_name", "broad_sector", "sub_sector", "roe_pct", "roce_pct"}.issubset(payload[0].keys())


def test_company_detail_returns_profile():
    response = client.get("/api/v1/companies/TCS")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "TCS"
    assert body["company_name"]
    assert body["latest_ratios"]["year"]


def test_invalid_company_returns_404():
    response = client.get("/api/v1/companies/INVALIDCOMPANY")
    assert response.status_code == 404
