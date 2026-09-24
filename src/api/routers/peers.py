"""Peer-group percentile routes."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from ..database import get_db

router = APIRouter(prefix="/peers", tags=["peers"])


@router.get("/{group_name}")
def peer_group(
    group_name: str, connection: sqlite3.Connection = Depends(get_db)
) -> list[dict[str, object]]:
    """Return companies and their latest percentile ranks within a peer group."""
    rows = connection.execute(
        """SELECT p.company_id, c.company_name, p.metric, p.value, p.percentile_rank, p.year
		   FROM peer_percentiles p JOIN companies c ON c.id = p.company_id
		   WHERE p.peer_group_name = ? ORDER BY c.company_name, p.metric""",
        [group_name],
    ).fetchall()
    if not rows:
        raise HTTPException(status_code=404, detail="Peer group not found")
    return [dict(row) for row in rows]
