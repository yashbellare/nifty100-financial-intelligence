"""Screener routes."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from ..database import get_db

router = APIRouter(prefix="/screener", tags=["screener"])


def _number(value: str | None, name: str) -> float | None:
    """Parse an optional numeric filter and report invalid values as HTTP 400."""
    if value is None or value == "":
        return None
    try:
        return float(value)
    except ValueError as error:
        raise HTTPException(
            status_code=400, detail=f"{name} must be numeric"
        ) from error


@router.get("")
def screen_companies(
    min_roe: str | None = None,
    max_de: str | None = None,
    min_fcf: str | None = None,
    sector: str | None = None,
    min_rev_cagr_5yr: str | None = None,
    min_pat_cagr_5yr: str | None = None,
    max_pe: str | None = None,
    connection: sqlite3.Connection = Depends(get_db),
) -> list[dict[str, object]]:
    """Return latest ratio snapshots matching the requested screener filters."""
    filters = {
        "min_roe": _number(min_roe, "min_roe"),
        "max_de": _number(max_de, "max_de"),
        "min_fcf": _number(min_fcf, "min_fcf"),
        "min_rev_cagr_5yr": _number(min_rev_cagr_5yr, "min_rev_cagr_5yr"),
        "min_pat_cagr_5yr": _number(min_pat_cagr_5yr, "min_pat_cagr_5yr"),
        "max_pe": _number(max_pe, "max_pe"),
    }
    sql = """
		SELECT c.id, c.company_name, s.broad_sector, r.*,
			   m.pe_ratio AS pe_ratio
		FROM companies c
		LEFT JOIN sectors s ON s.company_id = c.id
		JOIN financial_ratios r ON r.company_id = c.id
		LEFT JOIN market_cap m ON m.company_id = c.id AND CAST(m.year AS TEXT) = r.year
		WHERE r.year = (SELECT MAX(r2.year) FROM financial_ratios r2 WHERE r2.company_id = c.id)
	"""
    params: list[object] = []
    if filters["min_roe"] is not None:
        sql += " AND r.return_on_equity_pct >= ?"
        params.append(filters["min_roe"])
    if filters["max_de"] is not None:
        sql += " AND r.debt_to_equity <= ?"
        params.append(filters["max_de"])
    if filters["min_fcf"] is not None:
        sql += " AND r.free_cash_flow_cr >= ?"
        params.append(filters["min_fcf"])
    if filters["min_rev_cagr_5yr"] is not None:
        sql += " AND r.revenue_cagr_5yr >= ?"
        params.append(filters["min_rev_cagr_5yr"])
    if filters["min_pat_cagr_5yr"] is not None:
        sql += " AND r.pat_cagr_5yr >= ?"
        params.append(filters["min_pat_cagr_5yr"])
    if filters["max_pe"] is not None:
        sql += " AND m.pe_ratio <= ?"
        params.append(filters["max_pe"])
    if sector:
        sql += " AND LOWER(s.broad_sector) = LOWER(?)"
        params.append(sector)
    sql += " ORDER BY COALESCE(r.composite_quality_score, r.return_on_equity_pct) DESC, c.company_name"
    return [dict(row) for row in connection.execute(sql, params).fetchall()]
