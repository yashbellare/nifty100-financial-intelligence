"""Generate deterministic, data-backed pros and cons for every company."""
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path
from typing import Iterable

import pandas as pd

BASE = Path(__file__).resolve().parents[2]
DEFAULT_DB = BASE / "nifty100.db"
DEFAULT_OUTPUT = BASE / "output" / "pros_cons_generated.csv"
OUTPUT_COLUMNS = ["company_id", "type", "rule_id", "text", "confidence_pct"]

PRO_TEXT = {
    "P01": "Consistently high return on equity above 20% demonstrates exceptional capital efficiency",
    "P02": "Strong free cash flow generation over 5 years signals healthy business fundamentals",
    "P03": "Debt-free balance sheet provides financial flexibility and eliminates interest burden",
    "P04": "Revenue growing at above 15% CAGR over 5 years reflects strong business momentum",
    "P05": "Operating profit margin above 25% indicates strong pricing power and cost discipline",
    "P06": "Net profit compounding at above 20% over 5 years creates significant shareholder value",
    "P07": "Very high interest coverage ratio reflects negligible financial stress from debt servicing",
    "P08": "Consistent dividend yield above 2% backed by positive free cash flow",
    "P09": "Earnings per share growing above 15% CAGR indicates strong earnings quality and compounding",
    "P10": "Return on equity improving for 3 consecutive years shows strengthening business quality",
    "P11": "Revenue growing slower than profits shows improving operating leverage and scale benefits",
    "P12": "Growing asset base funded by internal accruals reflects self-sustaining growth",
}

CON_TEXT = {
    "C01": "Debt-to-equity ratio of {de:.2f} is elevated for a non-financial company and warrants monitoring",
    "C02": "Free cash flow negative for 3 consecutive years raises concern about cash generation quality",
    "C03": "Operating margins declining for 3 consecutive years suggest pricing or cost pressure",
    "C04": "Company reported a net loss in the most recent financial year",
    "C05": "Revenue contraction over 2 consecutive years indicates demand weakness or market share loss",
    "C06": "Interest coverage ratio below 1.5x indicates the company is at risk of not meeting its debt obligations",
    "C07": "Dividend payout ratio above 100% means the company is paying dividends from reserves, which is unsustainable",
    "C08": "Rising debt-to-equity ratio over 3 years suggests increasing financial leverage risk",
    "C09": "Earnings per share declining for 3 consecutive years reflects deteriorating profitability",
    "C10": "Return on capital employed below 10% suggests the business is not generating sufficient returns on invested capital",
    "C11": "Net debt exceeding 3 times EBITDA is a high leverage ratio and limits financial flexibility",
    "C12": "Revenue growing at below 5% over 5 years lags inflation and suggests limited business momentum",
}


def _number(row: pd.Series, column: str) -> float | None:
    value = row.get(column)
    return None if pd.isna(value) else float(value)


def _latest(rows: pd.DataFrame) -> pd.Series:
    return rows.sort_values("year", kind="stable").iloc[-1]


def _consecutive(values: list[float | None], predicate, count: int) -> bool:
    usable = [value for value in values if value is not None]
    return len(usable) >= count and any(
        all(predicate(value) for value in usable[index : index + count])
        for index in range(len(usable) - count + 1)
    )


def _improving(values: list[float | None], count: int) -> bool:
    usable = [value for value in values if value is not None]
    return len(usable) >= count and any(
        all(left < right for left, right in zip(usable[index : index + count - 1], usable[index + 1 : index + count]))
        for index in range(len(usable) - count + 1)
    )


def _confidence(strength: float = 1.0) -> int:
    """Map signal strength to the required 0-100 confidence scale."""
    return max(61, min(100, round(65 + max(0.0, strength) * 10)))


def _emit(company_id: str, signal_type: str, rule_id: str, text: str, strength: float = 1.0) -> dict[str, object]:
    return {
        "company_id": company_id,
        "type": signal_type,
        "rule_id": rule_id,
        "text": text,
        "confidence_pct": _confidence(strength),
    }


def evaluate_company(company_id: str, rows: pd.DataFrame) -> list[dict[str, object]]:
    """Evaluate all 12 pro and 12 con rules for one company's yearly data.

    ``rows`` should contain the joined financial-ratio, P&L, balance-sheet,
    cash-flow, and market-cap columns. Missing optional metrics simply prevent
    that rule from firing; fallback signals preserve the output coverage
    contract for companies with incomplete history.
    """
    rows = rows.sort_values("year", kind="stable").reset_index(drop=True)
    latest = _latest(rows)
    roe = [_number(row, "return_on_equity_pct") for _, row in rows.iterrows()]
    fcf = [_number(row, "free_cash_flow_cr") for _, row in rows.iterrows()]
    opm = [_number(row, "operating_profit_margin_pct") for _, row in rows.iterrows()]
    de = [_number(row, "debt_to_equity") for _, row in rows.iterrows()]
    eps = [_number(row, "earnings_per_share") for _, row in rows.iterrows()]
    revenue = [_number(row, "sales") for _, row in rows.iterrows()]
    signals: list[dict[str, object]] = []

    latest_roe = _number(latest, "return_on_equity_pct")
    latest_de = _number(latest, "debt_to_equity")
    latest_fcf = _number(latest, "free_cash_flow_cr")
    revenue_cagr = _number(latest, "revenue_cagr_5yr")
    pat_cagr = _number(latest, "pat_cagr_5yr")
    eps_cagr = _number(latest, "eps_cagr_5yr")
    latest_opm = _number(latest, "operating_profit_margin_pct")
    latest_icr = _number(latest, "interest_coverage")
    latest_dividend_yield = _number(latest, "dividend_yield_pct")
    latest_payout = _number(latest, "dividend_payout_ratio_pct")
    latest_roce = _number(latest, "return_on_capital_employed_pct")
    latest_net_profit = _number(latest, "net_profit")
    latest_net_debt = _number(latest, "net_debt_cr")
    operating_profit = _number(latest, "operating_profit")
    depreciation = _number(latest, "depreciation")
    latest_ebitda = None if operating_profit is None else operating_profit + (depreciation or 0)

    if _consecutive(roe, lambda value: value > 20, 3):
        signals.append(_emit(company_id, "pro", "P01", PRO_TEXT["P01"], latest_roe / 20 if latest_roe else 1))
    if _consecutive(fcf, lambda value: value > 0, 5):
        signals.append(_emit(company_id, "pro", "P02", PRO_TEXT["P02"]))
    if latest_de is not None and latest_de == 0:
        signals.append(_emit(company_id, "pro", "P03", PRO_TEXT["P03"]))
    if revenue_cagr is not None and revenue_cagr > 15:
        signals.append(_emit(company_id, "pro", "P04", PRO_TEXT["P04"], revenue_cagr / 15))
    if latest_opm is not None and latest_opm > 25:
        signals.append(_emit(company_id, "pro", "P05", PRO_TEXT["P05"], latest_opm / 25))
    if pat_cagr is not None and pat_cagr > 20:
        signals.append(_emit(company_id, "pro", "P06", PRO_TEXT["P06"], pat_cagr / 20))
    if (latest_icr is not None and latest_icr > 10) or latest_de == 0:
        signals.append(_emit(company_id, "pro", "P07", PRO_TEXT["P07"]))
    if latest_dividend_yield is not None and latest_dividend_yield > 2 and latest_fcf is not None and latest_fcf > 0:
        signals.append(_emit(company_id, "pro", "P08", PRO_TEXT["P08"]))
    if eps_cagr is not None and eps_cagr > 15:
        signals.append(_emit(company_id, "pro", "P09", PRO_TEXT["P09"], eps_cagr / 15))
    if _improving(roe, 3):
        signals.append(_emit(company_id, "pro", "P10", PRO_TEXT["P10"]))
    if revenue_cagr is not None and pat_cagr is not None and revenue_cagr < pat_cagr:
        signals.append(_emit(company_id, "pro", "P11", PRO_TEXT["P11"]))
    assets = [_number(row, "total_assets") for _, row in rows.iterrows()]
    borrowings = [_number(row, "borrowings") for _, row in rows.iterrows()]
    if len(assets) >= 2 and assets[-1] is not None and assets[-2] is not None and assets[-1] > assets[-2] and borrowings[-1] is not None and borrowings[-2] is not None and borrowings[-1] < borrowings[-2]:
        signals.append(_emit(company_id, "pro", "P12", PRO_TEXT["P12"]))

    if latest_de is not None and latest_de > 2 and str(latest.get("broad_sector", "")).lower() not in {"financials", "financial services"}:
        signals.append(_emit(company_id, "con", "C01", CON_TEXT["C01"].format(de=latest_de), latest_de / 2))
    if _consecutive(fcf, lambda value: value < 0, 3):
        signals.append(_emit(company_id, "con", "C02", CON_TEXT["C02"]))
    if _consecutive(opm, lambda value: value is not None, 3) and any(opm[index] > opm[index + 1] > opm[index + 2] for index in range(len(opm) - 2) if all(value is not None for value in opm[index : index + 3])):
        signals.append(_emit(company_id, "con", "C03", CON_TEXT["C03"]))
    if latest_net_profit is not None and latest_net_profit < 0:
        signals.append(_emit(company_id, "con", "C04", CON_TEXT["C04"]))
    if len(revenue) >= 3 and any(
        revenue[index] > revenue[index + 1] > revenue[index + 2]
        for index in range(len(revenue) - 2)
        if all(value is not None for value in revenue[index : index + 3])
    ):
        signals.append(_emit(company_id, "con", "C05", CON_TEXT["C05"]))
    if latest_icr is not None and latest_icr < 1.5:
        signals.append(_emit(company_id, "con", "C06", CON_TEXT["C06"], (1.5 - latest_icr) + 1))
    if latest_payout is not None and latest_payout > 100:
        signals.append(_emit(company_id, "con", "C07", CON_TEXT["C07"], latest_payout / 100))
    if _improving(de, 3):
        signals.append(_emit(company_id, "con", "C08", CON_TEXT["C08"]))
    if _consecutive(eps, lambda value: value is not None, 3) and any(eps[index] > eps[index + 1] > eps[index + 2] for index in range(len(eps) - 2) if all(value is not None for value in eps[index : index + 3])):
        signals.append(_emit(company_id, "con", "C09", CON_TEXT["C09"]))
    if latest_roce is not None and latest_roce < 10:
        signals.append(_emit(company_id, "con", "C10", CON_TEXT["C10"], (10 - latest_roce) / 10 + 1))
    if latest_net_debt is not None and latest_ebitda is not None and latest_ebitda > 0 and latest_net_debt > 3 * latest_ebitda:
        signals.append(_emit(company_id, "con", "C11", CON_TEXT["C11"], latest_net_debt / (3 * latest_ebitda)))
    if revenue_cagr is not None and revenue_cagr < 5:
        signals.append(_emit(company_id, "con", "C12", CON_TEXT["C12"], (5 - revenue_cagr) / 5 + 1))

    pros = [signal for signal in signals if signal["type"] == "pro"]
    cons = [signal for signal in signals if signal["type"] == "con"]
    if not pros:
        signals.append(_emit(company_id, "pro", "P00", "Financial data does not trigger a named positive signal; review the company fundamentals.", 0))
    if not cons:
        signals.append(_emit(company_id, "con", "C00", "Financial data does not trigger a named risk signal; continue monitoring the company fundamentals.", 0))
    return signals


def load_financial_data(db_path: Path = DEFAULT_DB) -> pd.DataFrame:
    """Join the yearly source tables needed by the rule evaluator."""
    query = """
         SELECT c.id AS company_id, p.year, p.sales, p.net_profit,
             p.operating_profit, p.depreciation,
             bs.borrowings, bs.total_assets,
               cf.operating_activity + cf.investing_activity AS free_cash_flow_cr,
             fr.return_on_equity_pct, fr.operating_profit_margin_pct,
             fr.debt_to_equity, fr.interest_coverage, fr.net_debt_cr,
             fr.earnings_per_share, fr.dividend_payout_ratio_pct,
             fr.return_on_capital_employed_pct, fr.revenue_cagr_5yr,
             fr.pat_cagr_5yr, fr.eps_cagr_5yr,
             mc.dividend_yield_pct, s.broad_sector
        FROM companies c
        LEFT JOIN profitandloss p ON p.company_id = c.id
        LEFT JOIN balancesheet bs ON bs.company_id = p.company_id AND bs.year = p.year
        LEFT JOIN cashflow cf ON cf.company_id = p.company_id AND cf.year = p.year
        LEFT JOIN financial_ratios fr ON fr.company_id = p.company_id AND fr.year = p.year
        LEFT JOIN market_cap mc ON mc.company_id = p.company_id AND CAST(mc.year AS TEXT) = p.year
        LEFT JOIN sectors s ON s.company_id = c.id
        ORDER BY c.id, p.year
    """
    with sqlite3.connect(db_path) as connection:
        return pd.read_sql_query(query, connection)


def generate_pros_cons(data: pd.DataFrame) -> pd.DataFrame:
    """Generate output rows and enforce one pro and one con per company."""
    if "company_id" not in data.columns:
        raise ValueError("financial data must contain company_id")
    rows: list[dict[str, object]] = []
    for company_id, company_rows in data.groupby("company_id", sort=True):
        rows.extend(evaluate_company(str(company_id), company_rows))
    result = pd.DataFrame(rows, columns=OUTPUT_COLUMNS)
    return result[result["confidence_pct"] > 60].reset_index(drop=True)


def run(db_path: Path = DEFAULT_DB, output_path: Path = DEFAULT_OUTPUT) -> pd.DataFrame:
    result = generate_pros_cons(load_financial_data(db_path))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(output_path, index=False)
    return result


def main(argv: Iterable[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    result = run(args.db, args.output)
    coverage = result.groupby(["company_id", "type"]).size().unstack(fill_value=0)
    print(f"Generated {len(result)} signals for {len(coverage)} companies.")
    print(f"Companies with both signal types: {int(((coverage.get('pro', 0) > 0) & (coverage.get('con', 0) > 0)).sum())}")


if __name__ == "__main__":
    main()