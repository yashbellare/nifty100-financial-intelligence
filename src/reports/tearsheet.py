"""Generate a compact, two-page company tearsheet with ReportLab.

The renderer reads the canonical SQLite tables and the generated NLP output,
so it can be used independently of the Streamlit dashboard.
"""

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
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph
from reportlab.pdfgen import canvas

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = PROJECT_ROOT / "nifty100.db"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "reports" / "tearsheets"
PAGE_WIDTH, PAGE_HEIGHT = A4
NAVY = colors.HexColor("#102A43")
BLUE = colors.HexColor("#2F80ED")
GREEN = colors.HexColor("#2E8B57")
RED = colors.HexColor("#B23A48")
INK = colors.HexColor("#243B53")
MUTED = colors.HexColor("#627D98")
GRID = colors.HexColor("#D9E2EC")
PALE = colors.HexColor("#F5F7FA")
FONT_DIR = Path(__import__("reportlab").__file__).resolve().parent / "fonts"
pdfmetrics.registerFont(TTFont("Vera", str(FONT_DIR / "Vera.ttf")))
pdfmetrics.registerFont(TTFont("VeraBd", str(FONT_DIR / "VeraBd.ttf")))


def _year(value) -> int | None:
    match = re.search(r"20\d{2}", str(value))
    return int(match.group()) if match else None


def _number(value) -> float | None:
    converted = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return None if pd.isna(converted) else float(converted)


def _fmt(value, suffix="", decimals=1) -> str:
    number = _number(value)
    return "N/A" if number is None else f"{number:,.{decimals}f}{suffix}"


def _safe_text(value, fallback="N/A") -> str:
    if value is None or pd.isna(value):
        return fallback
    return str(value).replace("\n", " ").strip() or fallback


def _latest(frame: pd.DataFrame) -> pd.Series:
    if frame.empty:
        return pd.Series(dtype="object")
    rows = frame.copy()
    rows["year_number"] = rows["year"].map(_year)
    return rows.dropna(subset=["year_number"]).sort_values("year_number").iloc[-1]


def load_company_data(
    ticker: str, db_path: Path = DEFAULT_DB, output_dir: Path = PROJECT_ROOT / "output"
) -> dict[str, object]:
    """Load all source data needed for one tearsheet."""
    ticker = str(ticker).strip().upper()
    with sqlite3.connect(db_path) as connection:
        company = pd.read_sql_query(
            "SELECT * FROM companies WHERE id = ?", connection, params=[ticker]
        )
        if company.empty:
            raise ValueError(f"Unknown company ticker: {ticker}")
        tables = {}
        for table in ("profitandloss", "balancesheet", "cashflow", "financial_ratios"):
            tables[table] = pd.read_sql_query(
                f"SELECT * FROM {table} WHERE company_id = ?",
                connection,
                params=[ticker],
            )
        sector = pd.read_sql_query(
            "SELECT * FROM sectors WHERE company_id = ?", connection, params=[ticker]
        )

    pros_cons = pd.DataFrame(columns=["type", "text", "confidence_pct"])
    generated = output_dir / "pros_cons_generated.csv"
    if generated.exists():
        pros_cons = pd.read_csv(generated)
        pros_cons = pros_cons[pros_cons["company_id"].astype(str).str.upper() == ticker]
    allocation = pd.DataFrame(columns=["year", "pattern_label"])
    allocation_path = output_dir / "capital_allocation.csv"
    if allocation_path.exists():
        allocation = pd.read_csv(allocation_path)
        allocation = allocation[
            allocation["company_id"].astype(str).str.upper() == ticker
        ]
    company_row = company.iloc[0]
    sector_row = sector.iloc[0] if not sector.empty else pd.Series(dtype="object")
    return {
        "ticker": ticker,
        "company": company_row,
        "sector": sector_row,
        "pl": tables["profitandloss"],
        "bs": tables["balancesheet"],
        "cf": tables["cashflow"],
        "ratios": tables["financial_ratios"],
        "pros_cons": pros_cons,
        "allocation": allocation,
    }


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()["BodyText"]
    return {
        "body": ParagraphStyle(
            "body",
            parent=base,
            fontName="Vera",
            fontSize=7.2,
            leading=9.2,
            textColor=INK,
            alignment=TA_LEFT,
        ),
        "small": ParagraphStyle(
            "small",
            parent=base,
            fontName="Vera",
            fontSize=6.5,
            leading=8,
            textColor=MUTED,
        ),
        "section": ParagraphStyle(
            "section",
            parent=base,
            fontName="VeraBd",
            fontSize=10,
            leading=12,
            textColor=NAVY,
        ),
        "bullet": ParagraphStyle(
            "bullet",
            parent=base,
            fontName="Vera",
            fontSize=7.1,
            leading=9.2,
            leftIndent=9,
            firstLineIndent=-7,
            textColor=INK,
        ),
    }


def _paragraph(
    pdf: canvas.Canvas,
    text: str,
    x: float,
    y_top: float,
    width: float,
    style: ParagraphStyle,
    max_height: float | None = None,
) -> float:
    paragraph = Paragraph(text, style)
    _, height = paragraph.wrap(width, max_height or PAGE_HEIGHT)
    if max_height is not None:
        height = min(height, max_height)
    paragraph.drawOn(pdf, x, y_top - height)
    return height


def _section(
    pdf: canvas.Canvas,
    title: str,
    x: float,
    y: float,
    width: float,
    style: ParagraphStyle,
) -> None:
    pdf.setFillColor(NAVY)
    pdf.rect(x, y - 3, width, 1.5, fill=1, stroke=0)
    _paragraph(pdf, title, x, y - 7, width, style)


def _draw_header(
    pdf: canvas.Canvas, company: pd.Series, sector: pd.Series, ticker: str, page: int
) -> None:
    pdf.setFillColor(NAVY)
    pdf.rect(0, PAGE_HEIGHT - 34 * mm, PAGE_WIDTH, 34 * mm, fill=1, stroke=0)
    name = _safe_text(company.get("company_name"), ticker)
    pdf.setFillColor(colors.white)
    pdf.setFont("VeraBd", 19)
    pdf.drawString(16 * mm, PAGE_HEIGHT - 16 * mm, name[:52])
    pdf.setFont("Vera", 9)
    pdf.drawString(
        16 * mm,
        PAGE_HEIGHT - 23 * mm,
        f"{ticker}  |  {_safe_text(sector.get('broad_sector'))}  |  {_safe_text(sector.get('sub_sector'))}",
    )
    pdf.setFont("Vera", 7)
    pdf.drawRightString(
        PAGE_WIDTH - 16 * mm,
        PAGE_HEIGHT - 28 * mm,
        f"NIFTY 100 INTELLIGENCE  |  PAGE {page}",
    )


def _draw_kpi_tiles(
    pdf: canvas.Canvas,
    ratios: pd.DataFrame,
    pl: pd.DataFrame,
    bs: pd.DataFrame,
    x: float,
    y: float,
    width: float,
    styles: dict[str, ParagraphStyle],
) -> None:
    latest_ratio, latest_pl, latest_bs = _latest(ratios), _latest(pl), _latest(bs)
    metrics = [
        ("ROE", _fmt(latest_ratio.get("return_on_equity_pct"), "%")),
        ("ROCE", _fmt(latest_ratio.get("return_on_capital_employed_pct"), "%")),
        ("Revenue CAGR 5Y", _fmt(latest_ratio.get("revenue_cagr_5yr"), "%")),
        ("Net profit", _fmt(latest_pl.get("net_profit"), " cr", 0)),
        ("Debt / Equity", _fmt(latest_ratio.get("debt_to_equity"), "x")),
        ("Borrowings", _fmt(latest_bs.get("borrowings"), " cr", 0)),
    ]
    gap = 4 * mm
    tile_width = (width - 2 * gap) / 3
    tile_height = 22 * mm
    for index, (label, value) in enumerate(metrics):
        row, column = divmod(index, 3)
        tile_x = x + column * (tile_width + gap)
        tile_y = y - row * (tile_height + gap)
        pdf.setFillColor(PALE)
        pdf.setStrokeColor(GRID)
        pdf.roundRect(
            tile_x,
            tile_y - tile_height,
            tile_width,
            tile_height,
            2 * mm,
            fill=1,
            stroke=1,
        )
        pdf.setFillColor(MUTED)
        pdf.setFont("VeraBd", 7)
        pdf.drawString(tile_x + 5 * mm, tile_y - 7 * mm, label.upper())
        pdf.setFillColor(NAVY)
        pdf.setFont("VeraBd", 14)
        pdf.drawString(tile_x + 5 * mm, tile_y - 16 * mm, value)


def _chart_frame(
    pdf: canvas.Canvas, title: str, x: float, y: float, width: float, height: float
) -> tuple[float, float, float, float]:
    pdf.setFillColor(colors.white)
    pdf.setStrokeColor(GRID)
    pdf.roundRect(x, y, width, height, 2 * mm, fill=1, stroke=1)
    pdf.setFillColor(NAVY)
    pdf.setFont("VeraBd", 8)
    pdf.drawString(x + 5 * mm, y + height - 8 * mm, title)
    return x + 10 * mm, y + 9 * mm, width - 15 * mm, height - 22 * mm


def _draw_bar_chart(
    pdf: canvas.Canvas,
    frame: pd.DataFrame,
    x: float,
    y: float,
    width: float,
    height: float,
) -> None:
    left, bottom, plot_width, plot_height = _chart_frame(
        pdf, "Revenue and net profit (INR cr)", x, y, width, height
    )
    values = (
        frame[["sales", "net_profit"]].apply(pd.to_numeric, errors="coerce").fillna(0)
    )
    maximum = max(float(values.max().max()), 1.0)
    scale = plot_height / maximum
    count = len(frame)
    group_width = plot_width / max(count, 1)
    for row_index, (_, row) in enumerate(frame.iterrows()):
        center = left + (row_index + 0.5) * group_width
        for offset, (column, color) in enumerate(
            (("sales", BLUE), ("net_profit", GREEN))
        ):
            value = max(float(row[column]), 0)
            bar_width = min(group_width * 0.32, 8 * mm)
            bar_x = center - bar_width + offset * bar_width
            pdf.setFillColor(color)
            pdf.rect(bar_x, bottom, bar_width - 0.5, value * scale, fill=1, stroke=0)
        pdf.setFillColor(MUTED)
        pdf.setFont("Vera", 5.2)
        pdf.drawCentredString(center, bottom - 6, str(int(row["year_number"])))
    pdf.setStrokeColor(GRID)
    pdf.line(left, bottom, left + plot_width, bottom)


def _draw_line_chart(
    pdf: canvas.Canvas,
    frame: pd.DataFrame,
    x: float,
    y: float,
    width: float,
    height: float,
) -> None:
    left, bottom, plot_width, plot_height = _chart_frame(
        pdf, "ROE and ROCE trend (%)", x, y, width, height
    )
    values = frame[["roe", "roce"]].apply(pd.to_numeric, errors="coerce")
    numeric = values.stack()
    low = min(float(numeric.min()) if not numeric.empty else 0, 0)
    high = max(float(numeric.max()) if not numeric.empty else 1, 1)
    span = max(high - low, 1)
    count = len(frame)
    points = []
    for column, color in (("roe", RED), ("roce", BLUE)):
        points.clear()
        for index, (_, row) in enumerate(frame.iterrows()):
            value = _number(row[column])
            if value is None:
                continue
            px = left + (index / max(count - 1, 1)) * plot_width
            py = bottom + ((value - low) / span) * plot_height
            points.append((px, py))
        if len(points) > 1:
            pdf.setStrokeColor(color)
            pdf.setLineWidth(1.2)
            pdf.lines(
                [
                    (
                        points[index][0],
                        points[index][1],
                        points[index + 1][0],
                        points[index + 1][1],
                    )
                    for index in range(len(points) - 1)
                ]
            )
        pdf.setFillColor(color)
        for px, py in points:
            pdf.circle(px, py, 1.5, fill=1, stroke=0)
    pdf.setFillColor(MUTED)
    pdf.setFont("Vera", 5.2)
    for index, (_, row) in enumerate(frame.iterrows()):
        px = left + (index / max(count - 1, 1)) * plot_width
        pdf.drawCentredString(px, bottom - 6, str(int(row["year_number"])))


def _draw_stacked_balance(
    pdf: canvas.Canvas,
    frame: pd.DataFrame,
    x: float,
    y: float,
    width: float,
    height: float,
) -> None:
    left, bottom, plot_width, plot_height = _chart_frame(
        pdf, "Balance sheet composition (INR cr)", x, y, width, height
    )
    columns = [("equity", GREEN), ("borrowings", RED), ("other", BLUE)]
    values = frame.copy()
    values["equity"] = values["equity_capital"].fillna(0) + values["reserves"].fillna(0)
    values["other"] = values["other_liabilities"].fillna(0)
    maximum = max(
        float((values[["equity", "borrowings", "other"]].sum(axis=1)).max()), 1.0
    )
    group_width = plot_width / max(len(values), 1)
    for index, (_, row) in enumerate(values.iterrows()):
        bar_x = left + index * group_width + group_width * 0.2
        bar_width = group_width * 0.6
        current_y = bottom
        for column, color in columns:
            pdf.setFillColor(color)
            bar_height = max(float(row[column]), 0) / maximum * plot_height
            pdf.rect(bar_x, current_y, bar_width, bar_height, fill=1, stroke=0)
            current_y += bar_height
        pdf.setFillColor(MUTED)
        pdf.setFont("Vera", 5.2)
        pdf.drawCentredString(
            bar_x + bar_width / 2, bottom - 6, str(int(row["year_number"]))
        )


def _draw_waterfall(
    pdf: canvas.Canvas,
    latest: pd.Series,
    x: float,
    y: float,
    width: float,
    height: float,
) -> None:
    left, bottom, plot_width, plot_height = _chart_frame(
        pdf, "Latest-year cash flow (INR cr)", x, y, width, height
    )
    entries = [
        ("CFO", _number(latest.get("operating_activity"))),
        ("CFI", _number(latest.get("investing_activity"))),
        ("CFF", _number(latest.get("financing_activity"))),
        ("Net", _number(latest.get("net_cash_flow"))),
    ]
    maximum = max(max(abs(value or 0) for _, value in entries), 1.0)
    scale = plot_height / (2 * maximum)
    zero = bottom + plot_height / 2
    group_width = plot_width / len(entries)
    for index, (label, value) in enumerate(entries):
        value = value or 0
        bar_height = abs(value) * scale
        bar_x = left + index * group_width + group_width * 0.2
        pdf.setFillColor(GREEN if value >= 0 else RED)
        pdf.rect(
            bar_x,
            zero if value >= 0 else zero - bar_height,
            group_width * 0.6,
            bar_height,
            fill=1,
            stroke=0,
        )
        pdf.setFillColor(MUTED)
        pdf.setFont("Vera", 6)
        pdf.drawCentredString(bar_x + group_width * 0.3, bottom - 7, label)
    pdf.setStrokeColor(GRID)
    pdf.line(left, zero, left + plot_width, zero)


def _draw_bullets(
    pdf: canvas.Canvas,
    items: list[str],
    x: float,
    y_top: float,
    width: float,
    style: ParagraphStyle,
    color: colors.Color,
) -> None:
    pdf.setFillColor(color)
    y = y_top
    for item in items[:6]:
        height = _paragraph(pdf, f"<b>-</b> {_safe_text(item)}", x, y, width, style)
        y -= height + 2


def _render(data: dict[str, object], output_path: Path) -> Path:
    styles = _styles()
    pdf = canvas.Canvas(str(output_path), pagesize=A4, pageCompression=0)
    company, sector = data["company"], data["sector"]
    ticker = data["ticker"]
    _draw_header(pdf, company, sector, ticker, 1)
    margin = 16 * mm
    content_width = PAGE_WIDTH - 2 * margin
    _draw_kpi_tiles(
        pdf,
        data["ratios"],
        data["pl"],
        data["bs"],
        margin,
        PAGE_HEIGHT - 42 * mm,
        content_width,
        styles,
    )

    pl = data["pl"].copy()
    pl["year_number"] = pl["year"].map(_year)
    pl = pl.dropna(subset=["year_number"]).sort_values("year_number").tail(10)
    if not pl.empty:
        _draw_bar_chart(
            pdf, pl, margin, 103 * mm, (content_width - 5 * mm) / 2, 65 * mm
        )
    ratios = data["ratios"].copy()
    ratios["year_number"] = ratios["year"].map(_year)
    bs = data["bs"].copy()
    bs["year_number"] = bs["year"].map(_year)
    trend = (
        ratios[
            ["year_number", "return_on_equity_pct", "return_on_capital_employed_pct"]
        ]
        .rename(
            columns={
                "return_on_equity_pct": "roe",
                "return_on_capital_employed_pct": "roce",
            }
        )
        .dropna(subset=["year_number"])
        .sort_values("year_number")
        .tail(10)
    )
    if not trend.empty:
        _draw_line_chart(
            pdf,
            trend,
            margin + (content_width + 5 * mm) / 2,
            103 * mm,
            (content_width - 5 * mm) / 2,
            65 * mm,
        )
    _paragraph(
        pdf,
        f"<b>Coverage:</b> {len(pl)} annual observations shown; latest financial year: {_safe_text(_latest(data['pl']).get('year'))}",
        margin,
        97 * mm,
        content_width,
        styles["small"],
    )
    pdf.showPage()

    _draw_header(pdf, company, sector, ticker, 2)
    bs_chart = (
        bs[
            [
                "year_number",
                "equity_capital",
                "reserves",
                "borrowings",
                "other_liabilities",
            ]
        ]
        .dropna(subset=["year_number"])
        .sort_values("year_number")
        .tail(10)
        .fillna(0)
    )
    if not bs_chart.empty:
        _draw_stacked_balance(
            pdf, bs_chart, margin, 181 * mm, (content_width - 5 * mm) / 2, 55 * mm
        )
    latest_cf = _latest(data["cf"])
    if not latest_cf.empty:
        _draw_waterfall(
            pdf,
            latest_cf,
            margin + (content_width + 5 * mm) / 2,
            181 * mm,
            (content_width - 5 * mm) / 2,
            55 * mm,
        )

    _section(
        pdf, "Pros", margin, 174 * mm, (content_width - 5 * mm) / 2, styles["section"]
    )
    _section(
        pdf,
        "Cons",
        margin + (content_width + 5 * mm) / 2,
        174 * mm,
        (content_width - 5 * mm) / 2,
        styles["section"],
    )
    signals = data["pros_cons"]
    pros = (
        signals[signals["type"].astype(str).str.lower() == "pro"]["text"].tolist()
        if not signals.empty
        else []
    )
    cons = (
        signals[signals["type"].astype(str).str.lower() == "con"]["text"].tolist()
        if not signals.empty
        else []
    )
    column_width = (content_width - 5 * mm) / 2
    _draw_bullets(pdf, pros, margin, 168 * mm, column_width, styles["bullet"], GREEN)
    _draw_bullets(
        pdf,
        cons,
        margin + (content_width + 5 * mm) / 2,
        168 * mm,
        column_width,
        styles["bullet"],
        RED,
    )

    allocation = data["allocation"]
    latest_pattern = (
        _safe_text(_latest(allocation).get("pattern_label"), "Not available")
        if not allocation.empty
        else "Not available"
    )
    badge_x, badge_y = margin, 37 * mm
    pdf.setFillColor(NAVY)
    pdf.roundRect(badge_x, badge_y, content_width, 14 * mm, 2 * mm, fill=1, stroke=0)
    pdf.setFillColor(colors.white)
    pdf.setFont("VeraBd", 8)
    pdf.drawString(badge_x + 5 * mm, badge_y + 9 * mm, "CAPITAL ALLOCATION")
    pdf.setFont("VeraBd", 13)
    pdf.drawRightString(
        badge_x + content_width - 5 * mm, badge_y + 7 * mm, latest_pattern[:42]
    )
    pdf.setFillColor(MUTED)
    pdf.setFont("Vera", 6.5)
    pdf.drawString(
        margin,
        27 * mm,
        "Source: canonical Nifty 100 SQLite financial statements and generated intelligence outputs.",
    )
    pdf.save()
    return output_path


def generate_tearsheet(
    ticker: str,
    output_path: Path | None = None,
    db_path: Path = DEFAULT_DB,
    output_dir: Path = PROJECT_ROOT / "output",
) -> Path:
    """Generate exactly one two-page PDF tearsheet and return its path."""
    ticker = str(ticker).strip().upper()
    destination = output_path or (DEFAULT_OUTPUT_DIR / f"{ticker}_tearsheet.pdf")
    destination.parent.mkdir(parents=True, exist_ok=True)
    return _render(load_company_data(ticker, db_path, output_dir), destination)


def main(argv: Iterable[str] | None = None) -> None:
    """Run the tearsheet command-line workflow."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ticker", help="Ticker to render")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = parser.parse_args(argv)
    tickers = (
        [args.ticker]
        if args.ticker
        else ["TCS", "HDFCBANK", "RELIANCE", "SUNPHARMA", "TATASTEEL"]
    )
    for ticker in tickers:
        path = generate_tearsheet(
            ticker, args.output_dir / f"{ticker}_tearsheet.pdf", args.db
        )
        print(path)


if __name__ == "__main__":
    main()
