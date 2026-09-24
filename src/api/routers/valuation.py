"""Historical market-cap and valuation routes."""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from ..database import get_db


router = APIRouter(prefix="/market-cap", tags=["valuation"])


@router.get("/{ticker}")
def market_cap_history(ticker: str, connection: sqlite3.Connection = Depends(get_db)) -> list[dict[str, object]]:
	"""Return historical valuation multiples for a company."""
	rows = connection.execute(
		"""SELECT year, market_cap_crore, enterprise_value_crore, pe_ratio, pb_ratio,
				  ev_ebitda, dividend_yield_pct
		   FROM market_cap WHERE company_id = ? AND year BETWEEN 2019 AND 2024 ORDER BY year""",
		[ticker.strip().upper()],
	).fetchall()
	if not rows:
		raise HTTPException(status_code=404, detail="Market-cap history not found")
	return [dict(row) for row in rows]