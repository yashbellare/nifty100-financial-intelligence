"""Cash-flow intelligence calculations and report generation."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Optional

import pandas as pd

from .cagr import cagr
from .ratios import (
	capital_allocation_pattern,
	capex_intensity,
	capex_intensity_label,
	cfo_quality_label,
	cfo_quality_score,
	free_cash_flow,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
REQUIRED_COLUMNS = [
	"company_id", "sector", "cfo_quality_score", "cfo_quality_label",
	"capex_intensity_pct", "capex_label", "fcf_cagr_5yr",
	"fcf_conversion_pct", "distress_flag", "deleveraging_flag",
	"capital_allocation_label",
]
ALLOCATION_COLUMNS = ["company_id", "year", "pattern_label"]
ALLOCATION_PATTERNS = [
	"Reinvestor", "Shareholder Returns", "Liquidating Assets", "Distress Signal",
	"Growth Funded by Debt", "Cash Accumulator", "Pre-Revenue", "Mixed",
]


def _number(value) -> Optional[float]:
	value = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
	return None if pd.isna(value) else float(value)


def _year(value) -> Optional[int]:
	match = pd.Series([value]).astype(str).str.extract(r"(\d{4})", expand=False).iloc[0]
	return int(match) if pd.notna(match) else None


def _clean_frame(frame: Optional[pd.DataFrame], columns: list[str]) -> pd.DataFrame:
	result = frame.copy() if frame is not None else pd.DataFrame(columns=columns)
	for column in columns:
		if column not in result:
			result[column] = pd.NA
	result = result[columns].copy()
	result["company_id"] = result["company_id"].astype(str).str.strip().str.upper()
	result["year_number"] = result["year"].map(_year)
	for column in columns[2:]:
		result[column] = pd.to_numeric(result[column], errors="coerce")
	return result.dropna(subset=["company_id", "year_number"])


def _latest_and_history(frame: pd.DataFrame, company_id: str):
	rows = frame[frame.company_id == company_id].sort_values("year_number")
	return (rows.iloc[-1] if not rows.empty else None), rows


def load_capital_allocation(path: Path = PROJECT_ROOT / "output" / "capital_allocation.csv") -> pd.DataFrame:
	"""Load the canonical company-year allocation patterns with normalized years."""
	if not path.exists():
		return pd.DataFrame(columns=ALLOCATION_COLUMNS + ["year_number"])
	allocation = pd.read_csv(path)
	for column in ALLOCATION_COLUMNS:
		if column not in allocation:
			allocation[column] = pd.NA
	allocation = allocation[ALLOCATION_COLUMNS].copy()
	allocation["company_id"] = allocation["company_id"].astype(str).str.strip().str.upper()
	allocation["pattern_label"] = allocation["pattern_label"].astype("string").str.strip()
	allocation["year_number"] = allocation["year"].map(_year)
	return allocation.dropna(subset=["company_id", "year_number", "pattern_label"])


def validate_capital_allocation(allocation: pd.DataFrame, company_ids: pd.Series | list[str]) -> pd.DataFrame:
	"""Return one validation row per expected company and source integrity check."""
	expected = pd.Series(company_ids, dtype="string").astype(str).str.strip().str.upper().drop_duplicates()
	present = set(allocation["company_id"])
	rows = []
	for company_id in expected:
		company_rows = allocation[allocation["company_id"] == company_id]
		duplicate_keys = int(company_rows.duplicated(["company_id", "year_number"]).sum())
		rows.append({
			"company_id": company_id,
			"status": "PASS" if company_id in present and duplicate_keys == 0 else "FAIL",
			"allocation_years": int(company_rows["year_number"].nunique()),
			"duplicate_company_years": duplicate_keys,
			"issue": "missing cash-flow coverage" if company_id not in present else ("duplicate company-year key" if duplicate_keys else ""),
		})
	unknown = sorted(present - set(expected))
	for company_id in unknown:
		rows.append({"company_id": company_id, "status": "FAIL", "allocation_years": int((allocation["company_id"] == company_id).sum()), "duplicate_company_years": 0, "issue": "not present in companies table"})
	return pd.DataFrame(rows, columns=["company_id", "status", "allocation_years", "duplicate_company_years", "issue"])


def latest_allocation_distribution(allocation: pd.DataFrame) -> pd.DataFrame:
	"""Count each pattern using the latest available year for each company."""
	latest = allocation.sort_values(["company_id", "year_number"]).groupby("company_id", as_index=False).tail(1)
	counts = latest.groupby("pattern_label")["company_id"].nunique()
	return pd.DataFrame({"pattern_label": ALLOCATION_PATTERNS, "company_count": [int(counts.get(pattern, 0)) for pattern in ALLOCATION_PATTERNS]})


def allocation_pattern_changes(allocation: pd.DataFrame) -> pd.DataFrame:
	"""Return company-year transitions where the allocation pattern changed."""
	ordered = allocation.sort_values(["company_id", "year_number"]).copy()
	ordered["prior_pattern"] = ordered.groupby("company_id")["pattern_label"].shift()
	ordered["prior_year"] = ordered.groupby("company_id")["year"].shift()
	changed = ordered[ordered["prior_pattern"].notna() & ordered["pattern_label"].ne(ordered["prior_pattern"])].copy()
	return changed.rename(columns={"prior_year": "from_year", "year": "to_year", "prior_pattern": "from_pattern", "pattern_label": "to_pattern"})[["company_id", "from_year", "to_year", "from_pattern", "to_pattern"]]


def _fcf_cagr(rows: pd.DataFrame) -> Optional[float]:
	if len(rows) < 2:
		return None
	latest = rows.iloc[-1]
	prior = rows.iloc[max(0, len(rows) - 6)]
	years = int(latest.year_number - prior.year_number)
	if years < 1:
		return None
	value, _ = cagr(prior.fcf, latest.fcf, years)
	return value


def compute_cashflow_intelligence(
	companies: pd.DataFrame,
	cashflow: pd.DataFrame,
	profitandloss: pd.DataFrame,
	balancesheet: pd.DataFrame,
	sectors: Optional[pd.DataFrame] = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
	"""Return one latest-year intelligence row and distress alerts per company."""
	cf = _clean_frame(cashflow, ["company_id", "year", "operating_activity", "investing_activity", "financing_activity"])
	pl = _clean_frame(profitandloss, ["company_id", "year", "sales", "net_profit"])
	bs = _clean_frame(balancesheet, ["company_id", "year", "borrowings"])

	company_ids = companies.iloc[:, 0].astype(str).str.strip().str.upper().tolist()
	sector_map = {}
	if sectors is not None and not sectors.empty:
		sector_id = "company_id" if "company_id" in sectors else sectors.columns[0]
		sector_column = "broad_sector" if "broad_sector" in sectors else sectors.columns[-1]
		sector_map = dict(zip(sectors[sector_id].astype(str).str.upper(), sectors[sector_column]))

	rows = []
	alerts = []
	for company_id in company_ids:
		latest_cf, cf_history = _latest_and_history(cf, company_id)
		_, pl_history = _latest_and_history(pl, company_id)
		_, bs_history = _latest_and_history(bs, company_id)
		if latest_cf is None:
			rows.append({"company_id": company_id, "sector": sector_map.get(company_id), **{column: None for column in REQUIRED_COLUMNS[2:]}})
			continue

		joined = cf_history[["company_id", "year_number", "operating_activity", "investing_activity"]].copy()
		joined = joined.merge(pl_history[["year_number", "sales", "net_profit"]], on="year_number", how="left")
		joined["fcf"] = [free_cash_flow(_number(cfo), _number(cfi)) for cfo, cfi in zip(joined.operating_activity, joined.investing_activity)]
		quality_history = joined.merge(
			pl_history[["year_number", "net_profit"]].rename(columns={"net_profit": "pat"}),
			on="year_number", how="left", suffixes=("", "_duplicate")
		)
		quality_ratios = [
			_number(cfo) / _number(pat)
			for cfo, pat in zip(quality_history.operating_activity, quality_history.pat)
			if _number(cfo) is not None and _number(pat) not in (None, 0)
		][-5:]
		score = cfo_quality_score(quality_ratios)
		latest_year = int(latest_cf.year_number)
		latest_pl = pl_history[pl_history.year_number == latest_year]
		latest_bs = bs_history[bs_history.year_number == latest_year]
		sales = _number(latest_pl.iloc[-1].sales) if not latest_pl.empty else None
		latest_pat = _number(latest_pl.iloc[-1].net_profit) if not latest_pl.empty else None
		latest_cfo = _number(latest_cf.operating_activity)
		latest_cfi = _number(latest_cf.investing_activity)
		latest_cff = _number(latest_cf.financing_activity)
		latest_fcf = free_cash_flow(latest_cfo, latest_cfi)
		intensity = capex_intensity(latest_cfi, sales)
		prior_bs = bs_history[bs_history.year_number < latest_year]
		prior_borrowings = _number(prior_bs.iloc[-1].borrowings) if not prior_bs.empty else None
		latest_borrowings = _number(latest_bs.iloc[-1].borrowings) if not latest_bs.empty else None
		distress = bool(latest_cfo is not None and latest_cfo < 0 and latest_cff is not None and latest_cff > 0)
		deleveraging = bool(latest_cff is not None and latest_cff < 0 and latest_borrowings is not None and prior_borrowings is not None and latest_borrowings < prior_borrowings)
		cfo_pat_ratio = latest_cfo / latest_pat if latest_cfo is not None and latest_pat not in (None, 0) else None
		allocation = capital_allocation_pattern(latest_cfo, latest_cfi, latest_cff, cfo_pat_ratio)
		conversion = latest_fcf / latest_cfo * 100 if latest_cfo not in (None, 0) else None
		result = {
			"company_id": company_id,
			"sector": sector_map.get(company_id),
			"cfo_quality_score": score,
			"cfo_quality_label": cfo_quality_label(score),
			"capex_intensity_pct": intensity,
			"capex_label": capex_intensity_label(intensity),
			"fcf_cagr_5yr": _fcf_cagr(joined[["year_number", "fcf"]].dropna()),
			"fcf_conversion_pct": conversion,
			"distress_flag": distress,
			"deleveraging_flag": deleveraging,
			"capital_allocation_label": allocation,
		}
		rows.append(result)
		if distress:
			alerts.append({"company_id": company_id, "sector": sector_map.get(company_id), "year": latest_cf.year, "cfo": latest_cfo, "cff": latest_cff, "latest_net_profit": latest_pat})

	return pd.DataFrame(rows, columns=REQUIRED_COLUMNS), pd.DataFrame(alerts, columns=["company_id", "sector", "year", "cfo", "cff", "latest_net_profit"])


def generate_cashflow_intelligence(db_path: Path = PROJECT_ROOT / "nifty100.db", output_dir: Path = PROJECT_ROOT / "output") -> pd.DataFrame:
	"""Read the database and write cash-flow intelligence plus Day 32 allocation artifacts."""
	with sqlite3.connect(db_path) as connection:
		tables = {name: pd.read_sql(f"SELECT * FROM {name}", connection) for name in ("companies", "cashflow", "profitandloss", "balancesheet", "sectors")}
	result, alerts = compute_cashflow_intelligence(**tables)
	output_dir.mkdir(parents=True, exist_ok=True)
	allocation = load_capital_allocation(output_dir / "capital_allocation.csv")
	validation = validate_capital_allocation(allocation, tables["companies"].iloc[:, 0])
	validation.to_csv(output_dir / "capital_allocation_validation.csv", index=False)
	latest = allocation.sort_values(["company_id", "year_number"]).groupby("company_id", as_index=False).tail(1)
	canonical_labels = latest.set_index("company_id")["pattern_label"]
	result["capital_allocation_label"] = result["company_id"].map(canonical_labels).fillna(result["capital_allocation_label"])
	latest_allocation_distribution(allocation).to_csv(output_dir / "capital_allocation_distribution.csv", index=False)
	allocation_pattern_changes(allocation).to_csv(output_dir / "pattern_changes.csv", index=False)
	result.to_excel(output_dir / "cashflow_intelligence.xlsx", index=False)
	alerts.to_csv(output_dir / "distress_alerts.csv", index=False)
	return result


__all__ = ["compute_cashflow_intelligence", "generate_cashflow_intelligence", "load_capital_allocation", "validate_capital_allocation", "latest_allocation_distribution", "allocation_pattern_changes", "cfo_quality_score", "cfo_quality_label", "capex_intensity", "capex_intensity_label", "capital_allocation_pattern"]


if __name__ == "__main__":
	generated = generate_cashflow_intelligence()
	print(f"Generated cash-flow intelligence for {len(generated)} companies")
