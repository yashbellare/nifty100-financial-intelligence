"""Parse analysis workbook metrics and cross-check available CAGR values."""

from __future__ import annotations

import argparse
import re
import sqlite3
from pathlib import Path
from typing import Iterable

import pandas as pd

BASE = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = BASE / "data" / "raw" / "analysis.xlsx"
DEFAULT_OUTPUT = BASE / "output"
DEFAULT_DB = BASE / "nifty100.db"

METRIC_COLUMNS = {
    "compounded_sales_growth": "revenue_cagr",
    "compounded_profit_growth": "pat_cagr",
    "stock_price_cagr": "stock_price_cagr",
    "roe": "roe",
}
OUTPUT_COLUMNS = ["company_id", "metric_type", "period_years", "value_pct"]
FAILURE_COLUMNS = ["company_id", "metric_type", "raw_value", "reason", "source_row"]
DIVERGENCE_COLUMNS = [
    "company_id",
    "metric_type",
    "period_years",
    "parsed_value_pct",
    "computed_value_pct",
    "divergence_pct",
    "status",
]

# The optional colon and flexible whitespace match the source workbook's variants.
VALUE_PATTERN = re.compile(
    r"(?P<period>\d+)\s*Years?:?\s*" r"(?P<value>[+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*%",
    re.IGNORECASE,
)


def parse_metric_value(value: object) -> tuple[int, float] | None:
    """Return ``(period_years, value_pct)`` for one source cell."""
    if pd.isna(value):
        return None
    match = VALUE_PATTERN.fullmatch(str(value).strip())
    if not match:
        return None
    return int(match.group("period")), float(match.group("value"))


def parse_analysis_frame(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Parse all target fields and return parsed rows plus unmatched cells."""
    required = {"company_id", *METRIC_COLUMNS}
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError(
            f"analysis data is missing required columns: {', '.join(missing)}"
        )

    parsed: list[dict[str, object]] = []
    failures: list[dict[str, object]] = []
    for source_index, row in frame.iterrows():
        company_id = (
            None
            if pd.isna(row["company_id"])
            else str(row["company_id"]).strip().upper()
        )
        for field, metric_type in METRIC_COLUMNS.items():
            raw_value = row[field]
            result = parse_metric_value(raw_value)
            if result is None:
                if not pd.isna(raw_value) and str(raw_value).strip():
                    reason = "pattern_mismatch"
                else:
                    reason = "missing_value"
                failures.append(
                    {
                        "company_id": company_id,
                        "metric_type": metric_type,
                        "raw_value": raw_value,
                        "reason": reason,
                        "source_row": int(source_index) + 3,
                    }
                )
                continue
            period_years, value_pct = result
            parsed.append(
                {
                    "company_id": company_id,
                    "metric_type": metric_type,
                    "period_years": period_years,
                    "value_pct": value_pct,
                }
            )

    return pd.DataFrame(parsed, columns=OUTPUT_COLUMNS), pd.DataFrame(
        failures, columns=FAILURE_COLUMNS
    )


def cross_validate(
    parsed: pd.DataFrame, ratios: pd.DataFrame, tolerance_pct: float = 5.0
) -> pd.DataFrame:
    """Flag parsed CAGR values that differ from matching ratio-engine values."""
    if parsed.empty or ratios.empty:
        return pd.DataFrame(columns=DIVERGENCE_COLUMNS)

    rows: list[dict[str, object]] = []
    for _, item in parsed.iterrows():
        if item["metric_type"] not in {"revenue_cagr", "pat_cagr"}:
            continue
        column = f"{item['metric_type']}_{int(item['period_years'])}yr"
        matches = (
            ratios[
                (ratios["company_id"].astype(str).str.upper() == item["company_id"])
                & ratios[column].notna()
            ]
            if column in ratios.columns
            else pd.DataFrame()
        )
        if matches.empty:
            continue
        if "year" in matches.columns:
            matches = matches.sort_values("year")
        computed = float(matches.iloc[-1][column])
        parsed_value = float(item["value_pct"])
        divergence = abs(parsed_value - computed)
        if divergence > tolerance_pct:
            rows.append(
                {
                    "company_id": item["company_id"],
                    "metric_type": item["metric_type"],
                    "period_years": item["period_years"],
                    "parsed_value_pct": parsed_value,
                    "computed_value_pct": computed,
                    "divergence_pct": divergence,
                    "status": "MANUAL_REVIEW",
                }
            )
    return pd.DataFrame(rows, columns=DIVERGENCE_COLUMNS)


def _load_ratios(db_path: Path) -> pd.DataFrame:
    if not db_path.exists():
        return pd.DataFrame()
    with sqlite3.connect(db_path) as connection:
        return pd.read_sql_query("SELECT * FROM financial_ratios", connection)


def run(
    input_path: Path = DEFAULT_INPUT,
    output_dir: Path = DEFAULT_OUTPUT,
    db_path: Path = DEFAULT_DB,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Generate Day 29 parser artifacts and return their dataframes."""
    frame = pd.read_excel(input_path, header=1)
    parsed, failures = parse_analysis_frame(frame)
    divergences = cross_validate(parsed, _load_ratios(db_path))
    output_dir.mkdir(parents=True, exist_ok=True)
    parsed.to_csv(output_dir / "analysis_parsed.csv", index=False)
    failures.to_csv(output_dir / "parse_failures.csv", index=False)
    divergences.to_csv(output_dir / "cagr_divergences.csv", index=False)
    return parsed, failures, divergences


def main(argv: Iterable[str] | None = None) -> None:
    """Run the parser command-line workflow."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = parser.parse_args(argv)
    parsed, failures, divergences = run(args.input, args.output_dir, args.db)
    print(
        f"Parsed {len(parsed)} values; logged {len(failures)} failures; "
        f"flagged {len(divergences)} manual-review divergences."
    )


if __name__ == "__main__":
    main()
