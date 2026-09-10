from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from src.dashboard.utils.db import get_companies, get_sectors


PROJECT_ROOT = Path(__file__).resolve().parents[3]


@st.cache_data(ttl=600)
def load_allocation():
	path = PROJECT_ROOT / "output" / "capital_allocation.csv"
	if not path.exists():
		return pd.DataFrame()
	data = pd.read_csv(path)
	if "year" in data:
		data["year_number"] = pd.to_numeric(data["year"].astype(str).str.extract(r"(20\d{2})")[0], errors="coerce")
		data = data.sort_values("year_number").groupby("company_id", as_index=False).tail(1)
	return data


st.title("Capital allocation map")
st.caption("Latest available cash-flow allocation pattern for each company.")
data = load_allocation()
if data.empty or "pattern_label" not in data:
	st.warning("Capital allocation data is not available.")
	st.stop()

companies = get_companies()[["company_id", "company_name"]]
sectors = get_sectors()[["company_id", "broad_sector"]]
data = data.merge(companies, on="company_id", how="left").merge(sectors, on="company_id", how="left")
data["Company"] = data["company_name"].fillna(data["company_id"])
counts = data.groupby("pattern_label", as_index=False).agg(Companies=("company_id", "nunique"))
figure = px.treemap(counts, path=["pattern_label"], values="Companies", color="Companies", color_continuous_scale="Tealgrn")
figure.update_layout(height=520, margin=dict(l=10, r=10, t=25, b=10))
selection = st.plotly_chart(figure, width="stretch", on_select="rerun", key="capital_treemap")

patterns = counts["pattern_label"].sort_values().tolist()
selected_pattern = st.selectbox("Pattern details", patterns)
try:
	points = selection.selection.point_indices
	if points:
		selected_pattern = patterns[points[0]]
except (AttributeError, IndexError, TypeError):
	pass

companies_in_pattern = data[data["pattern_label"] == selected_pattern][["Company", "company_id", "broad_sector"]].sort_values("Company")
st.subheader(f"{selected_pattern}: {len(companies_in_pattern)} companies")
st.dataframe(companies_in_pattern, width="stretch", hide_index=True)
