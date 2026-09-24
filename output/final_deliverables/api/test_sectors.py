from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)


def test_sectors_returns_all_loaded_sector_groups() -> None:
    response = client.get("/api/v1/sectors")
    assert response.status_code == 200
    sectors = response.json()
    assert len(sectors) == 10
    assert all(row["company_count"] > 0 for row in sectors)


def test_it_alias_returns_information_technology_companies() -> None:
    response = client.get("/api/v1/sectors/IT/companies")
    assert response.status_code == 200
    assert response.json()
    assert all(
        row["broad_sector"] == "Information Technology" for row in response.json()
    )
