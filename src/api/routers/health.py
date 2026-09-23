"""Health-check routes."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from time import monotonic

from fastapi import APIRouter, Depends, HTTPException

from ..database import get_db


router = APIRouter(tags=["health"])
_started_at = monotonic()
_TABLES = (
    "companies",
    "profitandloss",
    "balancesheet",
    "cashflow",
    "analysis",
    "documents",
    "prosandcons",
    "sectors",
    "stock_prices",
    "market_cap",
    "financial_ratios",
    "peer_groups",
)


@router.get("/health")
def health(connection: sqlite3.Connection = Depends(get_db)) -> dict[str, object]:
    """Return API availability and row counts for the SQLite data tables."""
    try:
        row_counts = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in _TABLES
        }
    except sqlite3.Error as error:
        raise HTTPException(status_code=503, detail="Database unavailable") from error

    return {
        "status": "ok",
        "db_row_counts": row_counts,
        "uptime_seconds": round(monotonic() - _started_at, 3),
        "version": "1.0.0",
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }