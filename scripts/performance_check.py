"""Run the Day 43 API and dashboard data-load performance checks."""
from __future__ import annotations

import sqlite3
import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi.testclient import TestClient

from src.api.database import DEFAULT_DB_PATH
from src.api.main import app
from src.dashboard.utils.db import get_companies, get_ratios


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output" / "perf_notes.md"


def apply_indexes() -> None:
    """Apply the schema indexes to the active SQLite database."""
    connection = sqlite3.connect(DEFAULT_DB_PATH)
    schema = (ROOT / "db" / "schema.sql").read_text(encoding="utf-8")
    connection.executescript(schema)
    connection.commit()
    connection.close()


def run() -> None:
    """Measure the requested Day 43 performance targets and write notes."""
    apply_indexes()
    client = TestClient(app)

    def request() -> float:
        started = time.perf_counter()
        response = client.get("/api/v1/screener", params={"min_roe": 15})
        response.raise_for_status()
        return time.perf_counter() - started

    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=10) as executor:
        api_times = list(executor.map(lambda _: request(), range(10)))
    api_total = time.perf_counter() - started

    companies = get_companies()
    tickers = companies["company_id"].dropna().astype(str).head(5).tolist()
    profile_times = []
    for ticker in tickers:
        started = time.perf_counter()
        get_ratios(ticker)
        profile_times.append(time.perf_counter() - started)

    notes = [
        "# Day 43 Performance Notes",
        "",
        f"- Concurrent screener calls: 10 completed in {api_total:.3f}s (target: <= 10s).",
        f"- Screener request median/max: {statistics.median(api_times):.3f}s / {max(api_times):.3f}s.",
        f"- Five dashboard ratio loads: median/max {statistics.median(profile_times):.3f}s / {max(profile_times):.3f}s (target: <= 3s each).",
        "- SQLite indexes applied for company/year joins and peer-group lookups.",
        "- API and Streamlit use separate ports by default: 8000 and 8501.",
    ]
    OUTPUT.write_text("\n".join(notes) + "\n", encoding="utf-8")
    print("\n".join(notes))


if __name__ == "__main__":
    run()