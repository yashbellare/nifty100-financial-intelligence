import re

import pandas as pd
import plotly.express as px
import streamlit as st

from src.dashboard.utils.db import get_companies, get_market_cap, get_pl, get_ratios, get_sectors


def year_number(value):
	text = str(value)
	match = re.search(r"20\d{2}", text)
	return int(match.group()) if match else None


def latest(frame):
	if frame.empty or "year" not in frame:
		return pd.Series(dtype="object")
	copy = frame.copy()
	copy["year_number"] = copy["year"].map(year_number)
	return copy.sort_values("year_number").iloc[-1]


@st.cache_data(ttl=600)
def sector_data():
	companies = get_companies().copy()
	sectors = get_sectors().copy()
	result = companies.merge(sectors[["company_id", "broad_sector", "sub_sector"]], on="company_id", how="left")
	rows = []
	for row in result.itertuples(index=False):
		ratios = latest(get_ratios(row.company_id))
		pl = latest(get_pl(row.company_id))
		market = latest(get_market_cap(row.company_id))
		rows.append({
			"company_id": row.company_id,
			"company_name": row.company_name,
			"broad_sector": row.broad_sector,
			"sub_sector": row.sub_sector,
			"Revenue": pd.to_numeric(pl.get("sales"), errors="coerce"),
			"ROE": pd.to_numeric(ratios.get("return_on_equity_pct"), errors="coerce"),
			"D/E": pd.to_numeric(ratios.get("debt_to_equity"), errors="coerce"),
			"Net profit margin": pd.to_numeric(ratios.get("net_profit_margin_pct"), errors="coerce"),
			"Market cap": pd.to_numeric(market.get("market_cap_crore"), errors="coerce"),
		})
	return pd.DataFrame(rows)


st.title("Sector analysis")
data = sector_data()
sectors = sorted(data["broad_sector"].dropna().unique().tolist())
if not sectors:
	st.warning("No sector data is available.")
	st.stop()
sector = st.selectbox("Sector", sectors)
selected = data[data["broad_sector"] == sector].copy()
if selected.empty:
	st.info("No companies are available for this sector.")
	st.stop()

plot_data = selected.dropna(subset=["Revenue", "ROE"]).copy()
if plot_data.empty:
	st.info("No complete revenue and ROE data is available for this sector.")
else:
	plot_data["Market cap"] = plot_data["Market cap"].fillna(1).clip(lower=1)
figure = px.scatter(plot_data, x="Revenue", y="ROE", size="Market cap", color="sub_sector", hover_name="company_name", hover_data=["company_id", "D/E"], size_max=48)
figure.update_layout(height=520, margin=dict(l=10, r=10, t=35, b=10), legend_title="Sub-sector")
if not plot_data.empty:
	st.plotly_chart(figure, width="stretch")

median_data = selected[["ROE", "D/E", "Net profit margin"]].median().rename_axis("Metric").reset_index(name="Median")
bar = px.bar(median_data, x="Metric", y="Median", color="Metric", title=f"{sector} median KPIs")
bar.update_layout(height=350, showlegend=False, margin=dict(l=10, r=10, t=45, b=10))
st.plotly_chart(bar, width="stretch")
