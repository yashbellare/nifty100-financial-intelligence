from pathlib import Path

import pandas as pd
import streamlit as st

from src.dashboard.utils.db import get_companies, get_ratios, get_sectors


PROJECT_ROOT = Path(__file__).resolve().parents[3]
OUTPUT_DIR = PROJECT_ROOT / "output"

METRICS = {
	"roe_min": ("ROE min (%)", "return_on_equity_pct", 0.0, -100.0, 100.0, 1.0),
	"de_max": ("D/E max", "debt_to_equity", 100.0, 0.0, 100.0, 1.0),
	"fcf_min": ("FCF min (cr)", "free_cash_flow_cr", 0.0, -10000.0, 100000.0, 100.0),
	"revenue_cagr_5yr_min": ("Revenue CAGR 5Y min (%)", "revenue_cagr_5yr", 0.0, -100.0, 100.0, 1.0),
	"pat_cagr_5yr_min": ("PAT CAGR 5Y min (%)", "pat_cagr_5yr", 0.0, -100.0, 100.0, 1.0),
	"opm_min": ("OPM min (%)", "operating_profit_margin_pct", 0.0, -100.0, 100.0, 1.0),
	"pe_max": ("P/E max", "pe_ratio", 60.0, 0.0, 200.0, 1.0),
	"pb_max": ("P/B max", "pb_ratio", 10.0, 0.0, 50.0, 0.5),
	"dividend_yield_min": ("Dividend yield min (%)", "dividend_yield", 0.0, 0.0, 20.0, 0.5),
	"icr_min": ("ICR min", "interest_coverage", 0.0, -10.0, 100.0, 1.0),
}

PRESETS = {
	"Quality": {"roe_min": 15.0, "de_max": 2.0, "fcf_min": 0.0, "revenue_cagr_5yr_min": 10.0, "opm_min": 10.0},
	"Value": {"pe_max": 20.0, "pb_max": 3.0, "de_max": 2.0, "dividend_yield_min": 1.0},
	"Growth": {"pat_cagr_5yr_min": 20.0, "revenue_cagr_5yr_min": 15.0, "de_max": 2.0},
	"Dividend": {"dividend_yield_min": 2.0, "fcf_min": 0.0},
	"Debt-Free": {"de_max": 0.0, "roe_min": 12.0, "fcf_min": 0.0},
	"Turnaround": {"revenue_cagr_5yr_min": 10.0, "fcf_min": 0.0, "de_max": 3.0},
}


def _year_number(value):
	match = pd.Series([value]).astype(str).str.extract(r"(20\d{2})").iloc[0, 0]
	return int(match) if pd.notna(match) else 0


def _numeric(series):
	return pd.to_numeric(series, errors="coerce")


@st.cache_data(ttl=600)
def load_screener_data():
	companies = get_companies().copy()
	sectors = get_sectors().copy()
	if not sectors.empty:
		companies = companies.merge(sectors[["company_id", "broad_sector", "sub_sector"]], on="company_id", how="left")

	ratio_rows = []
	for ticker in companies["company_id"].dropna().unique():
		ratios = get_ratios(ticker).copy()
		if not ratios.empty and "year" in ratios:
			ratios["year_number"] = ratios["year"].map(_year_number)
			ratio_rows.append(ratios.sort_values("year_number").iloc[-1])
	latest_ratios = pd.DataFrame(ratio_rows).drop(columns=["year_number"], errors="ignore")

	export_rows = []
	for path in OUTPUT_DIR.glob("*.csv"):
		try:
			candidate = pd.read_csv(path)
		except (OSError, ValueError):
			continue
		if "company_id" in candidate.columns:
			export_rows.append(candidate)
	exports = pd.concat(export_rows, ignore_index=True) if export_rows else pd.DataFrame()
	if not exports.empty:
		exports["year_number"] = exports.get("year", pd.Series(0, index=exports.index)).map(_year_number)
		exports = exports.sort_values("year_number").groupby("company_id", as_index=False).last()

	result = companies.merge(latest_ratios, on="company_id", how="left", suffixes=("", "_ratio"))
	if not exports.empty:
		result = result.merge(exports, on="company_id", how="left", suffixes=("", "_export"))

	aliases = {
		"revenue_cagr_5yr": ["revenue_cagr_5yr_export", "revenue_cagr_5yr"],
		"pat_cagr_5yr": ["pat_cagr_5yr_export", "pat_cagr_5yr"],
		"pe_ratio": ["pe_export", "pe_ratio"],
		"pb_ratio": ["pb_export", "pb_ratio"],
		"dividend_yield": ["dividend_yield_export", "dividend_yield"],
		"composite_score": ["composite_quality_score_export", "composite_quality_score"],
	}
	for target, candidates in aliases.items():
		available = [column for column in candidates if column in result.columns]
		if available:
			values = result[available[0]]
			for column in available[1:]:
				values = values.combine_first(result[column])
			result[target] = values

	result["composite_score"] = _numeric(result.get("composite_score", pd.Series(index=result.index)))
	if result["composite_score"].isna().all():
		score_parts = []
		for column in ["return_on_equity_pct", "operating_profit_margin_pct", "interest_coverage"]:
			if column in result:
				score_parts.append(_numeric(result[column]).rank(pct=True))
		if "debt_to_equity" in result:
			score_parts.append(_numeric(result["debt_to_equity"]).rank(pct=True, ascending=False))
		result["composite_score"] = pd.concat(score_parts, axis=1).mean(axis=1).mul(100) if score_parts else pd.NA
	return result


st.title("Stock screener")
st.caption("Tune the thresholds or start with a preset. Companies with unavailable data do not pass that filter.")

with st.sidebar:
	st.header("Screener filters")
	preset_columns = st.columns(2)
	for index, preset_name in enumerate(PRESETS):
		if preset_columns[index % 2].button(preset_name, key=f"preset_{preset_name}", width="stretch"):
			for key, value in PRESETS[preset_name].items():
				st.session_state[f"filter_{key}"] = value
			st.rerun()

	filters = {}
	for key, (label, _, default, minimum, maximum, step) in METRICS.items():
		state_key = f"filter_{key}"
		if state_key not in st.session_state:
			st.session_state[state_key] = default
		filters[key] = st.slider(label, minimum, maximum, step=step, key=state_key)

data = load_screener_data().copy()
for _, (_, column, *_rest) in METRICS.items():
	if column in data:
		data[column] = _numeric(data[column])

mask = pd.Series(True, index=data.index)
comparisons = {
	"roe_min": lambda values, threshold: values >= threshold,
	"de_max": lambda values, threshold: values <= threshold,
	"fcf_min": lambda values, threshold: values >= threshold,
	"revenue_cagr_5yr_min": lambda values, threshold: values >= threshold,
	"pat_cagr_5yr_min": lambda values, threshold: values >= threshold,
	"opm_min": lambda values, threshold: values >= threshold,
	"pe_max": lambda values, threshold: values <= threshold,
	"pb_max": lambda values, threshold: values <= threshold,
	"dividend_yield_min": lambda values, threshold: values >= threshold,
	"icr_min": lambda values, threshold: values >= threshold,
}
for key, threshold in filters.items():
	column = METRICS[key][1]
	values = data[column] if column in data else pd.Series(pd.NA, index=data.index, dtype="Float64")
	mask &= comparisons[key](values, threshold).fillna(False)

visible_columns = [
	"company_id", "company_name", "broad_sector", "composite_score",
	"return_on_equity_pct", "debt_to_equity", "free_cash_flow_cr", "revenue_cagr_5yr",
	"pat_cagr_5yr", "operating_profit_margin_pct", "pe_ratio", "pb_ratio",
	"dividend_yield", "interest_coverage",
]
results = data.loc[mask, [column for column in visible_columns if column in data.columns]].copy()
results = results.sort_values("composite_score", ascending=False, na_position="last")
st.subheader(f"{len(results)} companies match your filters")
st.dataframe(results.round(2), width="stretch", hide_index=True)
st.download_button("Download CSV", results.to_csv(index=False).encode("utf-8"), file_name="nifty100_screener_results.csv", mime="text/csv", icon=":material/download:")
