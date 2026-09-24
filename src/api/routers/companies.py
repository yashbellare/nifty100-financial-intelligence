"""Company routes for company master data and financial history endpoints."""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse

from ..database import get_db


router = APIRouter(prefix="/companies", tags=["companies"])
PROJECT_ROOT = Path(__file__).resolve().parents[3]
TEARSHEETS_DIR = PROJECT_ROOT / "reports" / "tearsheets"


def _row_to_dict(row: sqlite3.Row | None) -> dict[str, object] | None:
    """Return a sqlite Row as a plain dict."""
    if row is None:
        return None
    return dict(row)


def _parse_year(value: str | None) -> str | None:
    """Normalise a year input like YYYY or YYYY-MM to the canonical DB format."""
    if value is None:
        return None
    cleaned = str(value).strip()
    if not cleaned:
        return None
    if re.fullmatch(r"\d{4}-\d{2}", cleaned):
        return cleaned
    if re.fullmatch(r"\d{4}", cleaned):
        return cleaned
    return None


def _apply_year_filters(
    query: str,
    params: list[object],
    from_year: str | None,
    to_year: str | None,
) -> tuple[str, list[object]]:
    """Add year range filters to a company-history query."""
    if from_year is not None:
        query += " AND year >= ?"
        params.append(from_year)
    if to_year is not None:
        query += " AND year <= ?"
        params.append(to_year)
    return query, params


@router.get("")
def list_companies(
    sector: str | None = None,
    market_cap_category: str | None = None,
    search: str | None = None,
    connection: sqlite3.Connection = Depends(get_db),
) -> list[dict[str, object]]:
    """Return a filtered list of companies with their latest strategic summary."""
    base_sql = """
        SELECT
            c.id,
            c.company_name,
            s.broad_sector,
            s.sub_sector,
            c.roe_percentage AS roe_pct,
            c.roce_percentage AS roce_pct,
            s.market_cap_category
        FROM companies c
        LEFT JOIN sectors s ON s.company_id = c.id
    """
    conditions: list[str] = []
    params: list[object] = []

    if sector:
        conditions.append("LOWER(COALESCE(s.broad_sector, '')) = LOWER(?)")
        params.append(sector)
    if market_cap_category:
        conditions.append("LOWER(COALESCE(s.market_cap_category, '')) = LOWER(?)")
        params.append(market_cap_category)
    if search:
        conditions.append("(LOWER(c.company_name) LIKE LOWER(?) OR LOWER(c.id) LIKE LOWER(?))")
        search_term = f"%{search}%"
        params.extend([search_term, search_term])

    if conditions:
        base_sql += " WHERE " + " AND ".join(conditions)

    base_sql += " ORDER BY c.company_name ASC"
    rows = connection.execute(base_sql, params).fetchall()

    return [
        {
            "id": row["id"],
            "company_name": row["company_name"],
            "broad_sector": row["broad_sector"],
            "sub_sector": row["sub_sector"],
            "roe_pct": row["roe_pct"],
            "roce_pct": row["roce_pct"],
            "market_cap_category": row["market_cap_category"],
        }
        for row in rows
    ]


@router.get("/{ticker}")
def get_company(
    ticker: str,
    connection: sqlite3.Connection = Depends(get_db),
) -> dict[str, object]:
    """Return the full company profile with the latest ratio snapshot and sector metadata."""
    normalized_ticker = ticker.strip().upper()
    company_row = connection.execute(
        """
        SELECT c.*, s.broad_sector, s.sub_sector, s.index_weight_pct, s.market_cap_category
        FROM companies c
        LEFT JOIN sectors s ON s.company_id = c.id
        WHERE c.id = ?
        """,
        [normalized_ticker],
    ).fetchone()
    if company_row is None:
        raise HTTPException(status_code=404, detail="Company not found")

    latest_ratios = connection.execute(
        "SELECT * FROM financial_ratios WHERE company_id = ? ORDER BY year DESC LIMIT 1",
        [normalized_ticker],
    ).fetchone()

    sector_payload = {
        "company_id": normalized_ticker,
        "broad_sector": company_row["broad_sector"],
        "sub_sector": company_row["sub_sector"],
        "index_weight_pct": company_row["index_weight_pct"],
        "market_cap_category": company_row["market_cap_category"],
    }

    profile = dict(company_row)
    profile["roe_pct"] = profile.get("roe_percentage")
    profile["roce_pct"] = profile.get("roce_percentage")
    profile.pop("roe_percentage", None)
    profile.pop("roce_percentage", None)

    return {
        **profile,
        "sector": sector_payload,
        "latest_ratios": _row_to_dict(latest_ratios) or {},
    }


@router.get("/{ticker}/pl")
def get_company_pl(
    ticker: str,
    from_year: str | None = Query(default=None, alias="from_year"),
    to_year: str | None = Query(default=None, alias="to_year"),
    connection: sqlite3.Connection = Depends(get_db),
) -> list[dict[str, object]]:
    """Return the company's profit and loss history filtered by year range."""
    normalized_ticker = ticker.strip().upper()
    normalized_from = _parse_year(from_year)
    normalized_to = _parse_year(to_year)
    sql = "SELECT * FROM profitandloss WHERE company_id = ?"
    params: list[object] = [normalized_ticker]
    sql, params = _apply_year_filters(sql, params, normalized_from, normalized_to)
    sql += " ORDER BY year DESC"
    rows = connection.execute(sql, params).fetchall()
    return [_row_to_dict(row) for row in rows]


@router.get("/{ticker}/bs")
def get_company_bs(
    ticker: str,
    from_year: str | None = Query(default=None, alias="from_year"),
    to_year: str | None = Query(default=None, alias="to_year"),
    connection: sqlite3.Connection = Depends(get_db),
) -> list[dict[str, object]]:
    """Return the company's balance sheet history filtered by year range."""
    normalized_ticker = ticker.strip().upper()
    normalized_from = _parse_year(from_year)
    normalized_to = _parse_year(to_year)
    sql = "SELECT * FROM balancesheet WHERE company_id = ?"
    params: list[object] = [normalized_ticker]
    sql, params = _apply_year_filters(sql, params, normalized_from, normalized_to)
    sql += " ORDER BY year DESC"
    rows = connection.execute(sql, params).fetchall()
    return [_row_to_dict(row) for row in rows]


@router.get("/{ticker}/cashflow")
def get_company_cashflow(
    ticker: str,
    from_year: str | None = Query(default=None, alias="from_year"),
    to_year: str | None = Query(default=None, alias="to_year"),
    connection: sqlite3.Connection = Depends(get_db),
) -> list[dict[str, object]]:
    """Return the company's cash flow history filtered by year range."""
    normalized_ticker = ticker.strip().upper()
    normalized_from = _parse_year(from_year)
    normalized_to = _parse_year(to_year)
    sql = "SELECT * FROM cashflow WHERE company_id = ?"
    params: list[object] = [normalized_ticker]
    sql, params = _apply_year_filters(sql, params, normalized_from, normalized_to)
    sql += " ORDER BY year DESC"
    rows = connection.execute(sql, params).fetchall()
    return [_row_to_dict(row) for row in rows]


@router.get("/{ticker}/ratios")
def get_company_ratios(
    ticker: str,
    year: str | None = Query(default=None),
    connection: sqlite3.Connection = Depends(get_db),
) -> list[dict[str, object]] | dict[str, object]:
    """Return the company's ratio history or a single-year snapshot when a year is supplied."""
    normalized_ticker = ticker.strip().upper()
    normalized_year = _parse_year(year)
    sql = "SELECT * FROM financial_ratios WHERE company_id = ?"
    params: list[object] = [normalized_ticker]
    if normalized_year is not None:
        sql += " AND year = ?"
        params.append(normalized_year)
    sql += " ORDER BY year DESC"
    rows = connection.execute(sql, params).fetchall()
    history = [_row_to_dict(row) for row in rows]
    if normalized_year is not None:
        return history[0] if history else {}
    return history


@router.get("/{ticker}/tearsheet")
def get_company_tearsheet(ticker: str) -> FileResponse:
    """Download the generated PDF tearsheet for the given company."""
    normalized_ticker = ticker.strip().upper()
    candidate_paths = [
        TEARSHEETS_DIR / f"{normalized_ticker}_tearsheet.pdf",
        TEARSHEETS_DIR / f"{normalized_ticker}.pdf",
        PROJECT_ROOT / "reports" / "tearsheets" / f"{normalized_ticker}_tearsheet.pdf",
    ]
    for path in candidate_paths:
        if path.exists() and path.is_file():
            return FileResponse(path, media_type="application/pdf", filename=f"{normalized_ticker}_tearsheet.pdf")
    raise HTTPException(status_code=404, detail="Tearsheet not found")