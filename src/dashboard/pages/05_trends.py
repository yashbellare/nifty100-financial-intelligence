import re

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.dashboard.utils.db import get_companies, get_ratios


METRICS = {
	"Net profit margin": "net_profit_margin_pct",
	"Operating margin": "operating_profit_margin_pct",
	"ROE": "return_on_equity_pct",
	"D/E": "debt_to_equity",
	"Interest coverage": "interest_coverage",
	"FCF (cr)": "free_cash_flow_cr",
}


def year_number(value):
	match = re.search(r"20\d{2}", str(value))
	return int(match.group()) if match else None


companies = get_companies().copy()
st.title("Trend analysis")
st.caption("Compare up to three financial metrics across the available history.")

search = st.text_input("Search company", placeholder="Type a company name or ticker")
search_text = search.strip().lower()
matches = companies if not search_text else companies[
	companies["company_id"].astype(str).str.lower().str.contains(search_text, na=False)
	| companies["company_name"].astype(str).str.lower().str.contains(search_text, na=False)
]
if matches.empty:
	st.warning("Ticker not found - please try another")
	st.stop()

labels = {row.company_id: f"{row.company_name} ({row.company_id})" for row in matches.itertuples()}
ticker = st.selectbox("Company", matches["company_id"].tolist(), format_func=lambda value: labels.get(value, value))
metric_labels = st.multiselect("Metrics", list(METRICS), default=list(METRICS)[:2], max_selections=3)

history = get_ratios(ticker).copy()
if history.empty or not metric_labels:
	st.info("Select at least one metric with available data.")
	st.stop()

history["Year"] = history["year"].map(year_number)
history = history.dropna(subset=["Year"]).sort_values("Year")
selected_columns = [METRICS[label] for label in metric_labels if METRICS[label] in history.columns]
if not selected_columns:
	st.info("No selected metrics are available for this company.")
	st.stop()

chart_data = history.groupby("Year", as_index=False)[selected_columns].mean(numeric_only=True)
chart_data[selected_columns] = chart_data[selected_columns].apply(pd.to_numeric, errors="coerce")
chart_data = chart_data.dropna(subset=selected_columns, how="all")
if chart_data.empty:
	st.info("No numeric history is available for the selected metrics.")
	st.stop()
figure = go.Figure()
for label in metric_labels:
	column = METRICS[label]
	if column not in chart_data:
		continue
	values = pd.to_numeric(chart_data[column], errors="coerce")
	yoy = values.replace(0, pd.NA).pct_change().mul(100).replace([float("inf"), -float("inf")], pd.NA)
	text = ["" if pd.isna(value) else f"YoY {value:+.1f}%" for value in yoy]
	figure.add_trace(go.Scatter(x=chart_data["Year"], y=values, mode="lines+markers+text", text=text, textposition="top center", name=label, connectgaps=False))
figure.update_layout(height=520, hovermode="x unified", margin=dict(l=10, r=10, t=35, b=10), yaxis_title="Metric value")
st.plotly_chart(figure, width="stretch")
st.caption(f"{len(chart_data)} years of data available for {ticker}.")
