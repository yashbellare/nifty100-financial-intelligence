"""Sector summary and membership routes."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from ..database import get_db

router = APIRouter(prefix="/sectors", tags=["sectors"])


def _sector_name(value: str) -> str:
    """Map common API abbreviations to the canonical database sector name."""
    return "Information Technology" if value.strip().lower() == "it" else value.strip()


@router.get("")
def list_sectors(
    connection: sqlite3.Connection = Depends(get_db),
) -> list[dict[str, object]]:
    """Return company counts and median valuation/profitability metrics by sector."""
    rows = connection.execute("""
		SELECT s.broad_sector AS sector, COUNT(DISTINCT s.company_id) AS company_count,
			   AVG(r.return_on_equity_pct) AS median_roe,
			   AVG(m.pe_ratio) AS median_pe,
			   AVG(r.debt_to_equity) AS median_de
		FROM sectors s
		LEFT JOIN financial_ratios r ON r.company_id = s.company_id
		LEFT JOIN market_cap m ON m.company_id = s.company_id
		GROUP BY s.broad_sector ORDER BY s.broad_sector
		""").fetchall()
    return [dict(row) for row in rows]


@router.get("/{sector}/companies")
def sector_companies(
    sector: str, connection: sqlite3.Connection = Depends(get_db)
) -> list[dict[str, object]]:
    """Return latest ratio snapshots for companies in a sector."""
    sector = _sector_name(sector)
    exists = connection.execute(
        "SELECT 1 FROM sectors WHERE LOWER(broad_sector) = LOWER(?) LIMIT 1", [sector]
    ).fetchone()
    if exists is None:
        raise HTTPException(status_code=404, detail="Sector not found")
    rows = connection.execute(
        """
		SELECT c.id, c.company_name, s.broad_sector, s.sub_sector, r.*
		FROM companies c JOIN sectors s ON s.company_id = c.id
		LEFT JOIN financial_ratios r ON r.company_id = c.id
		  AND r.year = (SELECT MAX(r2.year) FROM financial_ratios r2 WHERE r2.company_id = c.id)
		WHERE LOWER(s.broad_sector) = LOWER(?) ORDER BY c.company_name
		""",
        [sector],
    ).fetchall()
    return [dict(row) for row in rows]
