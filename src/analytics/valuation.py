"""Valuation summary and relative P/E flag generation for Sprint 4."""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = PROJECT_ROOT / "nifty100.db"
DEFAULT_MARKET_CAP_PATH = PROJECT_ROOT / "data" / "supporting" / "market_cap.xlsx"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "output"

OUTPUT_COLUMNS = [
    "company_id",
    "company_name",
    "sector",
    "P/E",
    "P/B",
    "EV/EBITDA",
    "FCF_yield_pct",
    "5yr_median_PE",
    "PE_vs_sector_median_pct",
    "flag",
]


def _numeric(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Coerce optional numeric inputs without failing on source placeholders."""
    result = frame.copy()
    for column in columns:
        if column in result:
            result[column] = pd.to_numeric(result[column], errors="coerce")
    return result


def _latest_rows(frame: pd.DataFrame, key: str, year: str = "year") -> pd.DataFrame:
    """Return one latest dated row per key, preserving the source columns."""
    result = frame.copy()
    result["_year_value"] = pd.to_numeric(
        result[year].astype(str).str.extract(r"(\d{4})", expand=False),
        errors="coerce",
    )
    result = result.sort_values([key, "_year_value", year])
    return result.drop_duplicates(key, keep="last").drop(columns="_year_value")


def _load_sources(
    db_path: Path,
    market_cap_path: Path,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Load and normalize the four source tables used by the calculation."""
    market_cap = pd.read_excel(market_cap_path)
    with sqlite3.connect(db_path) as connection:
        companies = pd.read_sql_query(
            "SELECT id AS company_id, company_name FROM companies", connection
        )
        sectors = pd.read_sql_query(
            "SELECT company_id, broad_sector FROM sectors", connection
        )
        ratios = pd.read_sql_query(
            "SELECT company_id, year, free_cash_flow_cr FROM financial_ratios",
            connection,
        )

    market_cap = _numeric(
        market_cap,
        ["year", "market_cap_crore", "pe_ratio", "pb_ratio", "ev_ebitda"],
    )
    ratios = _numeric(ratios, ["free_cash_flow_cr"])
    market_cap["company_id"] = market_cap["company_id"].astype(str).str.strip()
    ratios["company_id"] = ratios["company_id"].astype(str).str.strip()
    companies["company_id"] = companies["company_id"].astype(str).str.strip()
    sectors["company_id"] = sectors["company_id"].astype(str).str.strip()
    return companies, sectors, market_cap, ratios


def _sector_medians(market_cap: pd.DataFrame, sectors: pd.DataFrame) -> pd.DataFrame:
    """Calculate latest-year positive P/E medians by broad sector."""
    latest_year = int(market_cap["year"].max())
    latest = market_cap[market_cap["year"].eq(latest_year)].copy()
    latest = latest.merge(sectors, on="company_id", how="left")
    latest["pe_ratio"] = latest["pe_ratio"].where(latest["pe_ratio"] > 0)
    return (
        latest.dropna(subset=["broad_sector", "pe_ratio"])
        .groupby("broad_sector", as_index=False)["pe_ratio"]
        .median()
        .rename(columns={"pe_ratio": "sector_median_pe"})
    )


def generate_valuation_outputs(
    db_path: Path = DEFAULT_DB_PATH,
    market_cap_path: Path = DEFAULT_MARKET_CAP_PATH,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> pd.DataFrame:
    """Generate valuation_summary.xlsx and valuation_flags.csv."""
    companies, sectors, market_cap, ratios = _load_sources(
        Path(db_path), Path(market_cap_path)
    )
    latest_market_cap = _latest_rows(market_cap, "company_id")
    latest_fcf = _latest_rows(ratios.dropna(subset=["free_cash_flow_cr"]), "company_id")

    summary = companies.merge(sectors, on="company_id", how="left")
    summary = summary.merge(
        latest_market_cap[
            ["company_id", "market_cap_crore", "pe_ratio", "pb_ratio", "ev_ebitda"]
        ],
        on="company_id",
        how="left",
    )
    summary = summary.merge(
        latest_fcf[["company_id", "free_cash_flow_cr"]], on="company_id", how="left"
    )
    summary = summary.merge(
        _sector_medians(market_cap, sectors), on="broad_sector", how="left"
    )

    summary["FCF_yield_pct"] = np.where(
        summary["market_cap_crore"].gt(0),
        summary["free_cash_flow_cr"] / summary["market_cap_crore"] * 100,
        np.nan,
    )
    summary["PE_vs_sector_median_pct"] = np.where(
        summary["sector_median_pe"].gt(0) & summary["pe_ratio"].gt(0),
        (summary["pe_ratio"] / summary["sector_median_pe"] - 1) * 100,
        np.nan,
    )
    summary["flag"] = "Fair"
    summary.loc[summary["PE_vs_sector_median_pct"] > 50, "flag"] = "Caution"
    summary.loc[summary["PE_vs_sector_median_pct"] < -30, "flag"] = "Discount"

    result = summary.rename(
        columns={
            "broad_sector": "sector",
            "pe_ratio": "P/E",
            "pb_ratio": "P/B",
            "ev_ebitda": "EV/EBITDA",
            "sector_median_pe": "5yr_median_PE",
        }
    )[OUTPUT_COLUMNS]
    result = result.sort_values("company_id").reset_index(drop=True)

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    result.to_excel(output_dir / "valuation_summary.xlsx", index=False)
    result[result["flag"].isin(["Caution", "Discount"])].to_csv(
        output_dir / "valuation_flags.csv", index=False
    )
    return result


def main() -> None:
    """Run the valuation analysis command-line workflow."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--market-cap", type=Path, default=DEFAULT_MARKET_CAP_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    result = generate_valuation_outputs(args.db, args.market_cap, args.output_dir)
    print(
        f"valuation rows={len(result)}; "
        f"flags={result['flag'].value_counts().to_dict()}"
    )


if __name__ == "__main__":
    main()
