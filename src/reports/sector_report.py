"""Generate sector summary PDFs from the canonical SQLite financial data."""

from __future__ import annotations

import argparse
import re
import sqlite3
from pathlib import Path
from typing import Iterable

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    LongTable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    TableStyle,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = PROJECT_ROOT / "nifty100.db"
DEFAULT_OUTPUT = PROJECT_ROOT / "reports" / "sector"
NAVY = colors.HexColor("#102A43")
INK = colors.HexColor("#243B53")
MUTED = colors.HexColor("#627D98")
GRID = colors.HexColor("#D9E2EC")
PALE = colors.HexColor("#F5F7FA")


def _year(value) -> int | None:
    match = re.search(r"20\d{2}", str(value))
    return int(match.group()) if match else None


def _number(value) -> float | None:
    converted = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return None if pd.isna(converted) else float(converted)


def _fmt(value, suffix="", decimals=1) -> str:
    number = _number(value)
    return "N/A" if number is None else f"{number:,.{decimals}f}{suffix}"


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()["BodyText"]
    return {
        "title": ParagraphStyle(
            "sector_title",
            parent=base,
            fontName="Helvetica-Bold",
            fontSize=17,
            leading=20,
            textColor=NAVY,
        ),
        "heading": ParagraphStyle(
            "sector_heading",
            parent=base,
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=9,
            textColor=colors.white,
        ),
        "cell": ParagraphStyle(
            "sector_cell",
            parent=base,
            fontName="Helvetica",
            fontSize=7,
            leading=8,
            textColor=INK,
            alignment=TA_LEFT,
        ),
        "small": ParagraphStyle(
            "sector_small",
            parent=base,
            fontName="Helvetica",
            fontSize=7.5,
            leading=9,
            textColor=MUTED,
        ),
    }


def _latest_by_company(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result["year_number"] = result["year"].map(_year)
    return (
        result.dropna(subset=["year_number"])
        .sort_values(["company_id", "year_number"])
        .groupby("company_id", as_index=False)
        .tail(1)
    )


def load_sector_data(db_path: Path = DEFAULT_DB) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return company master and latest-year joined KPI rows."""
    with sqlite3.connect(db_path) as connection:
        companies = pd.read_sql_query(
            "SELECT id AS company_id, company_name FROM companies", connection
        )
        sectors = pd.read_sql_query(
            "SELECT company_id, broad_sector FROM sectors", connection
        )
        ratios = pd.read_sql_query("SELECT * FROM financial_ratios", connection)
        pl = pd.read_sql_query(
            "SELECT company_id, year, sales, net_profit FROM profitandloss", connection
        )
        cf = pd.read_sql_query(
            "SELECT company_id, year, operating_activity, investing_activity FROM cashflow",
            connection,
        )
    latest_ratios = _latest_by_company(ratios)
    latest_pl = _latest_by_company(pl)
    latest_cf = _latest_by_company(cf)
    data = companies.merge(sectors, on="company_id", how="left")
    data = data.merge(
        latest_ratios[
            [
                "company_id",
                "year",
                "return_on_equity_pct",
                "return_on_capital_employed_pct",
                "operating_profit_margin_pct",
                "debt_to_equity",
                "revenue_cagr_5yr",
                "free_cash_flow_cr",
                "cfo_quality_score",
                "capital_allocation_pattern",
            ]
        ],
        on="company_id",
        how="left",
        suffixes=("", "_ratio"),
    )
    data = data.merge(
        latest_pl[["company_id", "net_profit"]], on="company_id", how="left"
    )
    data = data.merge(
        latest_cf[["company_id", "operating_activity", "investing_activity"]],
        on="company_id",
        how="left",
    )
    data["fcf_cr"] = pd.to_numeric(
        data["operating_activity"], errors="coerce"
    ) + pd.to_numeric(data["investing_activity"], errors="coerce")
    data["broad_sector"] = data["broad_sector"].fillna("Unclassified")
    return companies, data


def _metric_table(
    rows: pd.DataFrame, styles: dict[str, ParagraphStyle]
) -> list[list[object]]:
    columns = [
        ("Ticker", "company_id"),
        ("Company", "company_name"),
        ("ROE %", "return_on_equity_pct"),
        ("ROCE %", "return_on_capital_employed_pct"),
        ("OPM %", "operating_profit_margin_pct"),
        ("D/E", "debt_to_equity"),
        ("Rev CAGR 5Y %", "revenue_cagr_5yr"),
        ("FCF cr", "free_cash_flow_cr"),
        ("CFO score", "cfo_quality_score"),
        ("Allocation", "capital_allocation_pattern"),
    ]
    table = [[Paragraph(label, styles["heading"]) for label, _ in columns]]
    for _, row in rows.sort_values("company_id").iterrows():
        values = []
        for label, column in columns:
            if column in {"company_id", "company_name", "capital_allocation_pattern"}:
                value = str(row.get(column, "N/A"))
            else:
                value = _fmt(row.get(column))
            values.append(Paragraph(value, styles["cell"]))
        table.append(values)
    return table


def _build_sector_pdf(sector_name: str, rows: pd.DataFrame, output_path: Path) -> Path:
    styles = _styles()
    document = SimpleDocTemplate(
        str(output_path),
        pagesize=landscape(A4),
        leftMargin=10 * mm,
        rightMargin=10 * mm,
        topMargin=10 * mm,
        bottomMargin=10 * mm,
        title=f"{sector_name} sector report",
    )
    metrics = [
        "return_on_equity_pct",
        "return_on_capital_employed_pct",
        "operating_profit_margin_pct",
        "debt_to_equity",
        "revenue_cagr_5yr",
        "free_cash_flow_cr",
        "cfo_quality_score",
    ]
    medians = rows[metrics].apply(pd.to_numeric, errors="coerce").median()
    summary = "  |  ".join(
        f"{label}: {_fmt(medians[column])}"
        for label, column in [
            ("Median ROE", "return_on_equity_pct"),
            ("Median ROCE", "return_on_capital_employed_pct"),
            ("Median OPM", "operating_profit_margin_pct"),
            ("Median D/E", "debt_to_equity"),
            ("Median Rev CAGR", "revenue_cagr_5yr"),
            ("Median FCF", "free_cash_flow_cr"),
            ("Median CFO score", "cfo_quality_score"),
        ]
    )
    story = [
        Paragraph(sector_name, styles["title"]),
        Spacer(1, 3 * mm),
        Paragraph(
            f"{len(rows)} companies  |  Latest available company-year KPI snapshot",
            styles["small"],
        ),
        Spacer(1, 2 * mm),
        Paragraph(summary, styles["small"]),
        Spacer(1, 5 * mm),
    ]
    table = LongTable(
        _metric_table(rows, styles),
        repeatRows=1,
        colWidths=[
            17 * mm,
            43 * mm,
            16 * mm,
            17 * mm,
            17 * mm,
            14 * mm,
            22 * mm,
            19 * mm,
            20 * mm,
            43 * mm,
        ],
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                ("GRID", (0, 0), (-1, -1), 0.25, GRID),
                ("BACKGROUND", (0, 1), (-1, -1), colors.white),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, PALE]),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    story.append(table)
    document.build(story)
    return output_path


def generate_sector_reports(
    db_path: Path = DEFAULT_DB,
    output_dir: Path = DEFAULT_OUTPUT,
    include_overview: bool = True,
) -> list[Path]:
    """Generate one PDF per broad sector and an optional overall report."""
    _, data = load_sector_data(db_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for sector_name, rows in data.groupby("broad_sector", sort=True):
        filename = (
            re.sub(r"[^A-Za-z0-9]+", "_", str(sector_name)).strip("_").lower()
            or "unclassified"
        )
        paths.append(
            _build_sector_pdf(
                str(sector_name), rows, output_dir / f"{filename}_report.pdf"
            )
        )
    if include_overview:
        paths.append(
            _build_sector_pdf(
                "NIFTY 100 Overview", data, output_dir / "nifty100_report.pdf"
            )
        )
    return paths


def main(argv: Iterable[str] | None = None) -> None:
    """Run the sector report command-line workflow."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    for path in generate_sector_reports(args.db, args.output_dir):
        print(path)


if __name__ == "__main__":
    main()
