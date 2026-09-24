import sqlite3

from fastapi.testclient import TestClient

from src.api.database import DEFAULT_DB_PATH
from src.api.main import app


client = TestClient(app)


def test_dashboard_screener_source_and_api_have_same_qualifying_tickers() -> None:
    response = client.get("/api/v1/screener", params={"min_roe": 15})
    api_tickers = {row["id"] for row in response.json()}
    connection = sqlite3.connect(DEFAULT_DB_PATH)
    source_tickers = {
        row[0]
        for row in connection.execute(
            """SELECT company_id FROM financial_ratios
               WHERE year = (SELECT MAX(r2.year) FROM financial_ratios r2 WHERE r2.company_id = financial_ratios.company_id)
                 AND return_on_equity_pct >= 15"""
        )
    }
    connection.close()
    assert api_tickers == source_tickers
