"""Annual-report document routes."""
from __future__ import annotations

import sqlite3
from urllib.parse import urlparse

from fastapi import APIRouter, Depends

from ..database import get_db


router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("/{ticker}")
def company_documents(ticker: str, connection: sqlite3.Connection = Depends(get_db)) -> list[dict[str, object]]:
	"""Return annual-report links and a basic URL validity flag."""
	rows = connection.execute(
		"SELECT year, annual_report FROM documents WHERE company_id = ? ORDER BY year DESC",
		[ticker.strip().upper()],
	).fetchall()
	return [
		{**dict(row), "is_url_valid": bool(urlparse(str(row["annual_report"] or "")).scheme in {"http", "https"})}
		for row in rows
	]