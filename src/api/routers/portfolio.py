"""Portfolio-wide statistics routes."""
from __future__ import annotations

import sqlite3

import pandas as pd
from fastapi import APIRouter, Depends

from ..database import get_db


router = APIRouter(prefix="/portfolio", tags=["portfolio"])


@router.get("/stats")
def portfolio_stats(connection: sqlite3.Connection = Depends(get_db)) -> list[dict[str, object]]:
	"""Return percentile and summary statistics for the latest ratio snapshot."""
	frame = pd.read_sql_query(
		"""SELECT * FROM financial_ratios WHERE rowid IN
		   (SELECT rowid FROM financial_ratios GROUP BY company_id HAVING year = MAX(year))""",
		connection,
	)
	metrics = [
		"return_on_equity_pct", "debt_to_equity", "revenue_cagr_5yr", "pat_cagr_5yr",
		"free_cash_flow_cr", "operating_profit_margin_pct", "net_profit_margin_pct",
		"interest_coverage", "asset_turnover", "cfo_quality_score",
	]
	result = []
	for metric in metrics:
		if metric not in frame:
			continue
		values = pd.to_numeric(frame[metric], errors="coerce").dropna()
		if values.empty:
			continue
		result.append({"metric": metric, "p10": values.quantile(.10), "p25": values.quantile(.25),
					   "p50": values.quantile(.50), "p75": values.quantile(.75),
					   "p90": values.quantile(.90), "mean": values.mean(), "std": values.std()})
	return result