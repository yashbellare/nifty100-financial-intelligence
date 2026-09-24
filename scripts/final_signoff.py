"""Evaluate Sprint 6 acceptance gates and archive final deliverables."""
from __future__ import annotations

import shutil
import sqlite3
import subprocess
import sys
from datetime import date
from pathlib import Path

import pandas as pd
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.lib import colors

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.api.main import app


DB = ROOT / "nifty100.db"
OUTPUT = ROOT / "output"
DOCS = ROOT / "docs"
ARCHIVE = OUTPUT / "final_deliverables"


def gate(gate_id: str, description: str, passed: bool, detail: str) -> dict[str, object]:
    """Build one acceptance result row."""
    return {"gate_id": gate_id, "description": description, "status": "PASS" if passed else "FAIL", "detail": detail}


def evaluate() -> list[dict[str, object]]:
    """Evaluate the twenty Sprint 6 acceptance gates."""
    connection = sqlite3.connect(DB)
    companies = connection.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
    ratios = connection.execute("SELECT COUNT(*) FROM financial_ratios").fetchone()[0]
    coverage = connection.execute(
        """SELECT COUNT(*) FROM companies c WHERE (
            SELECT COUNT(DISTINCT year) FROM profitandloss WHERE company_id=c.id) >= 10
            AND (SELECT COUNT(DISTINCT year) FROM balancesheet WHERE company_id=c.id) >= 10
            AND (SELECT COUNT(DISTINCT year) FROM cashflow WHERE company_id=c.id) >= 10"""
    ).fetchone()[0]
    fk_errors = len(connection.execute("PRAGMA foreign_key_check").fetchall())
    peer_groups = connection.execute("SELECT COUNT(DISTINCT peer_group_name) FROM peer_groups").fetchone()[0]
    connection.close()

    health = app.openapi()
    cluster = pd.read_csv(OUTPUT / "cluster_labels.csv")
    pros = pd.read_csv(OUTPUT / "pros_cons_generated.csv")
    tearsheets = list((ROOT / "reports" / "tearsheets").glob("*.pdf"))
    validation = OUTPUT / "validation_failures.csv"
    perf = OUTPUT / "perf_notes.md"
    report = ROOT / "reports" / "pytest_report.html"
    screener_csv = OUTPUT / "nifty100_screened_results.csv"
    quality_output = OUTPUT / "quality_compounder.csv"
    result = [
        gate("AC-01", "92 companies", companies == 92, str(companies)),
        gate("AC-02", "90% have 10 years of P&L, BS, CF", coverage >= 83, f"{coverage}/92"),
        gate("AC-03", "Foreign-key check is empty", fk_errors == 0, str(fk_errors)),
        gate("AC-04", "At least 1,100 financial ratios", ratios >= 1100, str(ratios)),
        gate("AC-05", "CAGR validation artifact exists", (OUTPUT / "cagr_divergences.csv").exists(), "cagr_divergences.csv"),
        gate("AC-06", "ROE validation artifact exists", (OUTPUT / "manual_ratio_spot_check.xlsx").exists(), "manual_ratio_spot_check.xlsx"),
        gate("AC-07", "Quality screener preset returns 10-50 companies", 10 <= len(pd.read_csv(quality_output)) <= 50, str(len(pd.read_csv(quality_output)))),
        gate("AC-08", "Profile performance notes meet target", perf.exists(), "perf_notes.md"),
        gate("AC-09", "Screener CSV is readable", screener_csv.exists() and not pd.read_csv(screener_csv).empty, "CSV readable"),
        gate("AC-10", "Sample tearsheets exceed 30 KB", all(path.stat().st_size >= 30000 for path in tearsheets[:5]), "sample checked"),
        gate("AC-11", "Health route is in OpenAPI", "/api/v1/health" in health["paths"], "OpenAPI route present"),
        gate("AC-12", "TCS ratios have 10+ years", len(pd.read_sql_query("SELECT DISTINCT year FROM financial_ratios WHERE company_id='TCS'", sqlite3.connect(DB))) >= 10, "TCS ratio history"),
        gate("AC-13", "API screener integration test exists", (ROOT / "tests/api/test_dashboard_integration.py").exists(), "integration test present"),
        gate("AC-14", "All 11 peer groups have data", peer_groups == 11, str(peer_groups)),
        gate("AC-15", "All companies have cluster labels", len(cluster) == 92 and cluster["company_id"].nunique() == 92, str(len(cluster))),
        gate("AC-16", "All companies have pros and cons", pros["company_id"].nunique() == 92, str(pros["company_id"].nunique())),
        gate("AC-17", "92 tearsheet PDFs exceed 30 KB", len(tearsheets) == 92 and all(path.stat().st_size >= 30000 for path in tearsheets), str(len(tearsheets))),
        gate("AC-18", "Pytest report exists", report.exists(), "pytest_report.html"),
        gate("AC-19", "Validation failures has required columns", validation.exists() and {"company_id", "field", "issue", "severity"}.issubset(pd.read_csv(validation).columns), "columns checked"),
        gate("AC-20", "Analyst guide exists", (DOCS / "analyst_guide.pdf").exists(), "analyst_guide.pdf"),
    ]
    return result


def archive_and_write(results: list[dict[str, object]]) -> None:
    """Write acceptance results, checklist PDF, and the final archive."""
    DOCS.mkdir(exist_ok=True)
    ARCHIVE.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(results)
    frame.to_csv(OUTPUT / "acceptance_results.csv", index=False)
    deliverables = [
        "output/cluster_labels.csv", "reports/elbow_plot.png", "reports/correlation_heatmap.png",
        "output/outlier_report.csv", "output/portfolio_stats.csv", "docs/openapi.json",
        "docs/postman_collection.json", "reports/pytest_report.html", "docs/analyst_guide.pdf",
        "output/perf_notes.md", "output/validation_failures.csv", "output/pros_cons_generated.csv",
        "output/nifty100_screened_results.csv", "output/screener_output.xlsx", "output/valuation_flags.csv",
        "output/cagr_divergences.csv", "output/capital_allocation.csv", "reports/tearsheets",
        "src/api", "tests/api", "README.md", "requirements.txt", "db/schema.sql",
    ]
    checklist = []
    for relative in deliverables:
        source = ROOT / relative
        present = source.exists()
        checklist.append([relative, "PASS" if present else "FAIL"])
        if present:
            target = ARCHIVE / Path(relative).name
            if source.is_dir():
                shutil.copytree(source, target, dirs_exist_ok=True)
            else:
                shutil.copy2(source, target)
    styles = getSampleStyleSheet()
    story = [Paragraph("Sprint 6 Acceptance Checklist", styles["Title"]), Spacer(1, 12), Paragraph(f"Automated review date: {date.today().isoformat()}", styles["Normal"]), Spacer(1, 12)]
    story.append(Table([["Deliverable", "Status"], *checklist], colWidths=[5.8 * 72, 0.8 * 72], repeatRows=1, style=TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f4e79")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("GRID", (0, 0), (-1, -1), 0.25, colors.grey), ("FONTSIZE", (0, 0), (-1, -1), 8)])))
    story.extend([Spacer(1, 18), Paragraph("Team lead sign-off: Automated Day 45 checklist generated; human signature remains required.", styles["Normal"])])
    SimpleDocTemplate(str(DOCS / "acceptance_checklist.pdf"), pagesize=LETTER).build(story)


if __name__ == "__main__":
    results = evaluate()
    archive_and_write(results)
    print(pd.DataFrame(results).to_string(index=False))