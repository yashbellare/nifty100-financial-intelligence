"""Generate the one-page-per-company Sprint 5 portfolio summary PDF."""
from __future__ import annotations

import argparse
import re
import sqlite3
from pathlib import Path
from typing import Iterable

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle, PageBreak

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = PROJECT_ROOT / "nifty100.db"
DEFAULT_OUTPUT = PROJECT_ROOT / "reports" / "portfolio" / "portfolio_summary.pdf"
NAVY = colors.HexColor("#102A43")
INK = colors.HexColor("#243B53")
MUTED = colors.HexColor("#627D98")
GRID = colors.HexColor("#D9E2EC")
PALE = colors.HexColor("#F5F7FA")
UP = colors.HexColor("#2E8B57")
DOWN = colors.HexColor("#B23A48")


def _year(value) -> int | None:
    match = re.search(r"20\d{2}", str(value))
    return int(match.group()) if match else None


def _number(value) -> float | None:
    converted = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return None if pd.isna(converted) else float(converted)


def _fmt(value, suffix="", decimals=1) -> str:
    number = _number(value)
    return "N/A" if number is None else f"{number:,.{decimals}f}{suffix}"


def load_portfolio_data(db_path: Path = DEFAULT_DB) -> pd.DataFrame:
    """Return one latest-year row per company with a prior year for trends."""
    with sqlite3.connect(db_path) as connection:
        companies = pd.read_sql_query("SELECT id AS company_id, company_name FROM companies", connection)
        sectors = pd.read_sql_query("SELECT company_id, broad_sector FROM sectors", connection)
        ratios = pd.read_sql_query("SELECT * FROM financial_ratios", connection)
        pl = pd.read_sql_query("SELECT company_id, year, net_profit FROM profitandloss", connection)
        cf = pd.read_sql_query("SELECT company_id, year, operating_activity, investing_activity FROM cashflow", connection)

    ratios["year_number"] = ratios["year"].map(_year)
    pl["year_number"] = pl["year"].map(_year)
    cf["year_number"] = cf["year"].map(_year)
    ratios = ratios.dropna(subset=["year_number"]).sort_values(["company_id", "year_number"])
    pl = pl.dropna(subset=["year_number"]).sort_values(["company_id", "year_number"])
    cf = cf.dropna(subset=["year_number"]).sort_values(["company_id", "year_number"])
    latest = ratios.groupby("company_id", as_index=False).tail(1).copy()
    prior = ratios.groupby("company_id", as_index=False).nth(-2).reset_index(drop=True)
    prior = prior[["company_id", "return_on_equity_pct", "return_on_capital_employed_pct", "operating_profit_margin_pct", "debt_to_equity", "free_cash_flow_cr"]].rename(
        columns={column: f"prior_{column}" for column in ["return_on_equity_pct", "return_on_capital_employed_pct", "operating_profit_margin_pct", "debt_to_equity", "free_cash_flow_cr"]}
    )
    latest = latest.merge(companies, on="company_id", how="left").merge(sectors, on="company_id", how="left").merge(prior, on="company_id", how="left")
    latest_pl = pl.groupby("company_id", as_index=False).tail(1)[["company_id", "net_profit"]]
    latest_cf = cf.groupby("company_id", as_index=False).tail(1)
    latest = latest.merge(latest_pl, on="company_id", how="left").merge(latest_cf[["company_id", "operating_activity", "investing_activity"]], on="company_id", how="left")
    latest["free_cash_flow_cr"] = pd.to_numeric(latest["operating_activity"], errors="coerce") + pd.to_numeric(latest["investing_activity"], errors="coerce")
    return latest.sort_values("company_id").reset_index(drop=True)


def _trend(value, prior) -> str:
    current, previous = _number(value), _number(prior)
    if current is None or previous is None:
        return "-"
    if previous == 0:
        return "↑" if current > 0 else "↓" if current < 0 else "→"
    change = abs((current - previous) / abs(previous)) * 100
    if change <= 2:
        return "→"
    return "↑" if current > previous else "↓"


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()["BodyText"]
    return {
        "title": ParagraphStyle("portfolio_title", parent=base, fontName="Helvetica-Bold", fontSize=18, leading=22, textColor=colors.white),
        "subhead": ParagraphStyle("portfolio_subhead", parent=base, fontName="Helvetica", fontSize=9, leading=11, textColor=MUTED),
        "heading": ParagraphStyle("portfolio_heading", parent=base, fontName="Helvetica-Bold", fontSize=8, leading=9, textColor=colors.white, alignment=TA_LEFT),
        "cell": ParagraphStyle("portfolio_cell", parent=base, fontName="Helvetica", fontSize=9, leading=11, textColor=INK),
        "small": ParagraphStyle("portfolio_small", parent=base, fontName="Helvetica", fontSize=7.5, leading=9, textColor=MUTED),
    }


def _metric_rows(row: pd.Series, styles: dict[str, ParagraphStyle]) -> list[list[object]]:
    metrics = [
        ("ROE", "return_on_equity_pct", "%", 1),
        ("ROCE", "return_on_capital_employed_pct", "%", 1),
        ("OPM", "operating_profit_margin_pct", "%", 1),
        ("Revenue CAGR 5Y", "revenue_cagr_5yr", "%", 1),
        ("Debt / Equity", "debt_to_equity", "x", 2),
        ("Free Cash Flow", "free_cash_flow_cr", " cr", 0),
    ]
    rows = [[Paragraph("Metric", styles["heading"]), Paragraph("Latest", styles["heading"]), Paragraph("Trend", styles["heading"])]]
    for label, column, suffix, decimals in metrics:
        trend = _trend(row.get(column), row.get(f"prior_{column}"))
        trend_style = styles["cell"]
        if trend == "↑":
            trend_style = ParagraphStyle("up", parent=styles["cell"], textColor=UP)
        elif trend == "↓":
            trend_style = ParagraphStyle("down", parent=styles["cell"], textColor=DOWN)
        rows.append([Paragraph(label, styles["cell"]), Paragraph(_fmt(row.get(column), suffix, decimals), styles["cell"]), Paragraph(trend, trend_style)])
    return rows


def generate_portfolio_summary(db_path: Path = DEFAULT_DB, output_path: Path = DEFAULT_OUTPUT) -> Path:
    """Write a portfolio PDF with exactly one page for each company."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    styles = _styles()
    document = SimpleDocTemplate(str(output_path), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=18 * mm, bottomMargin=16 * mm, title="NIFTY 100 Portfolio Summary")
    story: list[object] = []
    for index, row in load_portfolio_data(db_path).iterrows():
        header = Table([[Paragraph(str(row.get("company_name") or row["company_id"]), styles["title"]), Paragraph(str(row["company_id"]), styles["title"])]], colWidths=[145 * mm, 25 * mm])
        header.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), NAVY), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7), ("TOPPADDING", (0, 0), (-1, -1), 9), ("BOTTOMPADDING", (0, 0), (-1, -1), 9)]))
        story.extend([header, Spacer(1, 6 * mm), Paragraph(f"{row.get('broad_sector') or 'Unclassified'}  |  Latest available year: {int(row['year_number'])}", styles["subhead"]), Spacer(1, 8 * mm)])
        table = Table(_metric_rows(row, styles), colWidths=[80 * mm, 55 * mm, 35 * mm], repeatRows=1)
        table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), NAVY), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, PALE]), ("GRID", (0, 0), (-1, -1), 0.35, GRID), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6), ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7)]))
        story.extend([table, Spacer(1, 10 * mm), Paragraph("Trend arrows compare the latest value with the preceding available year; changes within 2% are shown as flat.", styles["small"])])
        if index < len(load_portfolio_data(db_path)) - 1:
            story.append(PageBreak())
    document.build(story)
    return output_path


def main(argv: Iterable[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    print(generate_portfolio_summary(args.db, args.output))


if __name__ == "__main__":
    main()