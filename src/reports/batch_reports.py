"""Batch-generate Sprint 5 Day 34 tearsheet and sector report PDFs."""
from __future__ import annotations

import argparse
import csv
import re
import sqlite3
from pathlib import Path
from typing import Iterable

import pandas as pd

from .sector_report import DEFAULT_DB, DEFAULT_OUTPUT, generate_sector_reports
from .tearsheet import DEFAULT_OUTPUT_DIR, generate_tearsheet

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SKIPPED = PROJECT_ROOT / "output" / "skipped_tearsheets.csv"


def _year(value) -> int | None:
    match = re.search(r"20\d{2}", str(value))
    return int(match.group()) if match else None


def _company_coverage(db_path: Path) -> pd.DataFrame:
    with sqlite3.connect(db_path) as connection:
        companies = pd.read_sql_query("SELECT id AS company_id, company_name FROM companies ORDER BY id", connection)
        history = pd.read_sql_query("SELECT company_id, year FROM profitandloss", connection)
    history["year_number"] = history["year"].map(_year)
    coverage = history.dropna(subset=["year_number"]).groupby("company_id")["year_number"].nunique()
    companies["years_available"] = companies["company_id"].map(coverage).fillna(0).astype(int)
    return companies


def generate_batch_reports(db_path: Path = DEFAULT_DB, tearsheet_dir: Path = DEFAULT_OUTPUT_DIR, sector_dir: Path = DEFAULT_OUTPUT, skipped_path: Path = DEFAULT_SKIPPED) -> dict[str, object]:
    """Generate all eligible company PDFs, skipped log, and sector PDFs."""
    coverage = _company_coverage(db_path)
    skipped = coverage[coverage["years_available"] < 3].copy()
    skipped["reason"] = "fewer than 3 years of profit-and-loss data"
    skipped_path.parent.mkdir(parents=True, exist_ok=True)
    skipped[["company_id", "company_name", "years_available", "reason"]].to_csv(skipped_path, index=False)
    tearsheet_dir.mkdir(parents=True, exist_ok=True)
    generated = []
    errors = []
    for ticker in coverage.loc[coverage["years_available"] >= 3, "company_id"]:
        try:
            generated.append(generate_tearsheet(ticker, tearsheet_dir / f"{ticker}_tearsheet.pdf", db_path))
        except Exception as exc:  # Keep the batch moving and make failures inspectable.
            errors.append({"company_id": ticker, "reason": str(exc)})
    sector_paths = generate_sector_reports(db_path, sector_dir, include_overview=True)
    if errors:
        pd.DataFrame(errors).to_csv(tearsheet_dir.parent / "tearsheet_errors.csv", index=False)
    return {"generated": generated, "skipped": skipped, "sectors": sector_paths, "errors": errors}


def main(argv: Iterable[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--tearsheet-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--sector-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--skipped", type=Path, default=DEFAULT_SKIPPED)
    args = parser.parse_args(argv)
    result = generate_batch_reports(args.db, args.tearsheet_dir, args.sector_dir, args.skipped)
    print(f"Generated tearsheets: {len(result['generated'])}")
    print(f"Skipped tearsheets: {len(result['skipped'])}")
    print(f"Sector/overview PDFs: {len(result['sectors'])}")
    print(f"Tearsheet errors: {len(result['errors'])}")


if __name__ == "__main__":
    main()
