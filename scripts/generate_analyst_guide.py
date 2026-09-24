"""Generate the Day 44 analyst guide PDF."""

from __future__ import annotations

from pathlib import Path

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "analyst_guide.pdf"

PAGES = [
    (
        "Analyst Guide",
        "Nifty 100 Financial Intelligence Platform\nA practical guide to the dashboard, API, reports, and troubleshooting.",
    ),
    (
        "1. Start Here",
        "Install requirements, copy .env.template to .env, and confirm nifty100.db exists. Run make load for ETL, make ratios for KPI generation, and make valuation for valuation outputs.",
    ),
    (
        "2. Dashboard Home",
        "Open port 8501. Home summarizes company coverage, sector mix, quality scores, and current data freshness. Use the navigation menu to move between the eight screens.",
    ),
    (
        "3. Company Profile",
        "Choose a ticker to inspect master data, latest KPIs, P&L, balance sheet, cash flow, trend charts, pros and cons, and annual-report links. Missing values are displayed as unavailable rather than zero.",
    ),
    (
        "4. Screener",
        "Use the six presets or tune numeric filters. Results are ranked by composite quality score. Use Download CSV for a clean export that can be opened in Excel or shared with the research team.",
    ),
    (
        "5. Peers And Sectors",
        "Peer comparison shows percentile ranks and benchmark context. Sector analysis compares company counts, profitability, growth, and valuation. IT is accepted as an alias for Information Technology in the API.",
    ),
    (
        "6. Trends And Capital Allocation",
        "Trend analysis compares up to three metrics across years. Capital allocation groups companies by CFO, CFI, and CFF patterns and highlights changes between reporting periods.",
    ),
    (
        "7. Reports And Tearsheets",
        "The annual-report screen exposes source links. Pre-generated tearsheets are in reports/tearsheets. Download an individual PDF through the dashboard or GET /api/v1/companies/{ticker}/tearsheet.",
    ),
    (
        "8. API Cookbook",
        "Start uvicorn on port 8000. Useful calls include GET /api/v1/health, /companies, /companies/TCS/ratios, /screener?min_roe=15, /sectors, /peers/{group_name}, and /portfolio/stats. OpenAPI and Postman files are in docs/.",
    ),
    (
        "9. Troubleshooting And QA",
        "If data is missing, rerun ETL and inspect output/load_audit.csv and output/validation_failures.csv. Run pytest for regression checks, the performance harness for latency, and confirm ports 8000 and 8501 are available.",
    ),
]


def generate() -> None:
    """Write a ten-page analyst guide PDF."""
    OUTPUT.parent.mkdir(exist_ok=True)
    styles = getSampleStyleSheet()
    document = SimpleDocTemplate(
        str(OUTPUT), pagesize=LETTER, rightMargin=0.8 * inch, leftMargin=0.8 * inch
    )
    story = []
    for index, (title, body) in enumerate(PAGES):
        story.extend(
            [
                Spacer(1, 1.5 * inch),
                Paragraph(title, styles["Title"]),
                Spacer(1, 0.35 * inch),
            ]
        )
        story.append(
            Paragraph(
                body.replace("\n", "<br/>").replace("&", "&amp;"), styles["BodyText"]
            )
        )
        story.append(Spacer(1, 5 * inch))
        story.append(
            Paragraph(
                f"Nifty 100 Financial Intelligence | Page {index + 1} of {len(PAGES)}",
                styles["Normal"],
            )
        )
        if index < len(PAGES) - 1:
            story.append(PageBreak())
    document.build(story)


if __name__ == "__main__":
    generate()
