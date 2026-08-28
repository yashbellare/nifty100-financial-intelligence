"""Financial ratio calculation primitives for Sprint 2."""
from __future__ import annotations
from typing import Optional, Tuple

def _none_if_zero(x):
    return x is None or x == 0

def net_profit_margin(net_profit, sales):
    if _none_if_zero(sales): return None
    return net_profit / sales * 100 if net_profit is not None else None

def operating_profit_margin(operating_profit, sales):
    if _none_if_zero(sales): return None
    return operating_profit / sales * 100 if operating_profit is not None else None

def opm_crosscheck(computed, source, tolerance_pp=1.0):
    if computed is None or source is None: return False, None
    diff = computed - source
    return abs(diff) > tolerance_pp, diff

def return_on_equity(net_profit, equity_capital, reserves):
    denom = (equity_capital or 0) + (reserves or 0)
    if denom <= 0 or net_profit is None: return None
    return net_profit / denom * 100

def return_on_capital_employed(ebit, equity_capital, reserves, borrowings):
    denom = (equity_capital or 0) + (reserves or 0) + (borrowings or 0)
    if denom <= 0 or ebit is None: return None
    return ebit / denom * 100

def return_on_assets(net_profit, total_assets):
    if _none_if_zero(total_assets) or total_assets < 0 or net_profit is None: return None
    return net_profit / total_assets * 100

def debt_to_equity(borrowings, equity_capital, reserves):
    borrowings = borrowings or 0
    if borrowings == 0: return 0.0
    denom = (equity_capital or 0) + (reserves or 0)
    if denom <= 0: return None
    return borrowings / denom

def high_leverage_flag(de, broad_sector):
    return bool(de is not None and de > 5 and str(broad_sector).strip().lower() != "financials")

def interest_coverage(operating_profit, other_income, interest):
    if _none_if_zero(interest): return None
    return ((operating_profit or 0) + (other_income or 0)) / interest

def interest_coverage_label(icr):
    return "Debt Free" if icr is None else None

def interest_warning(icr, threshold=1.5):
    return bool(icr is not None and icr < threshold)

def net_debt(borrowings, investments):
    return (borrowings or 0) - (investments or 0)

def asset_turnover(sales, total_assets):
    if _none_if_zero(total_assets): return None
    return sales / total_assets if sales is not None else None

def free_cash_flow(operating_activity, investing_activity):
    return (operating_activity or 0) + (investing_activity or 0)

def capex(investing_activity):
    return abs(investing_activity) if investing_activity is not None else None

def capex_intensity(investing_activity, sales):
    if _none_if_zero(sales): return None
    return abs(investing_activity or 0) / sales * 100

def capex_intensity_label(pct):
    if pct is None: return None
    if pct < 3: return "Asset Light"
    if pct <= 8: return "Moderate"
    return "Capital Intensive"

def fcf_conversion_rate(fcf, operating_profit):
    if _none_if_zero(operating_profit): return None
    return fcf / operating_profit * 100 if fcf is not None else None

def cfo_quality_score(cfo_pat_ratios):
    vals = [x for x in cfo_pat_ratios if x is not None]
    return sum(vals)/len(vals) if vals else None

def cfo_quality_label(score):
    if score is None: return None
    if score > 1.0: return "High Quality"
    if score >= 0.5: return "Moderate"
    return "Accrual Risk"

def capital_allocation_pattern(cfo, cfi, cff, cfo_pat_ratio=None):
    s = lambda x: "+" if x is not None and x > 0 else "-" if x is not None and x < 0 else "0"
    pat = (s(cfo), s(cfi), s(cff))
    if pat == ("+","-","-"):
        return "Shareholder Returns" if cfo_pat_ratio is not None and cfo_pat_ratio > 1.0 else "Reinvestor"
    mapping = {
        ("+","+","-"): "Liquidating Assets",
        ("-","+","+"): "Distress Signal",
        ("-","-","+"): "Growth Funded by Debt",
        ("+","+","+"): "Cash Accumulator",
        ("-","-","-"): "Pre-Revenue",
        ("+","-","+"): "Mixed",
    }
    return mapping.get(pat, "Mixed")

def book_value_per_share(equity_capital, reserves, face_value=10):
    # Equity capital is in ₹ crore; shares = equity_capital crore / face_value.
    # Thus BVPS = (equity+reserves) / equity_capital * face_value.
    denom = equity_capital or 0
    if denom <= 0: return None
    return ((equity_capital or 0) + (reserves or 0)) / denom * face_value


def sector_relative_roce(roce, sector_benchmark):
    """Compare Financials ROCE to the peer-sector benchmark."""
    if roce is None or sector_benchmark is None:
        return None
    return roce - sector_benchmark
