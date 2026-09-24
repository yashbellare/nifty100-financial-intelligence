import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.dashboard.utils.db import (
    get_companies,
    get_peer_group_names,
    get_peers,
    get_ratios,
    get_sectors,
)


def _year_number(value):
    match = pd.Series([value]).astype(str).str.extract(r"(20\d{2})").iloc[0, 0]
    return int(match) if pd.notna(match) else 0


def _latest_ratio(ticker):
    ratios = get_ratios(ticker).copy()
    if ratios.empty or "year" not in ratios:
        return pd.Series(dtype="object")
    ratios["year_number"] = ratios["year"].map(_year_number)
    return ratios.sort_values("year_number").iloc[-1]


companies = get_companies().copy()
sectors = get_sectors().copy()
if not sectors.empty:
    companies = companies.merge(
        sectors[["company_id", "broad_sector", "sub_sector"]],
        on="company_id",
        how="left",
    )

groups = get_peer_group_names()
st.title("Peer comparison")
if not groups:
    st.warning("No peer groups are available.")
    st.stop()

group_name = st.selectbox("Peer group", groups)
membership = get_peers(group_name)
peer_ids = membership["company_id"].dropna().astype(str).tolist()
company_lookup = companies.set_index("company_id")

rows = []
for ticker in peer_ids:
    ratio = _latest_ratio(ticker)
    company = (
        company_lookup.loc[ticker]
        if ticker in company_lookup.index
        else pd.Series(dtype="object")
    )
    row = {
        "company_id": ticker,
        "company_name": company.get("company_name", ticker),
        "is_benchmark": False,
    }
    row.update(ratio.to_dict())
    row["roe"] = ratio.get("return_on_equity_pct", company.get("roe_percentage"))
    row["roce"] = company.get("roce_percentage")
    benchmark = membership[membership["company_id"].astype(str) == ticker]
    row["is_benchmark"] = bool(
        not benchmark.empty and benchmark.iloc[0].get("is_benchmark", False)
    )
    rows.append(row)

peer_data = pd.DataFrame(rows)
if peer_data.empty:
    st.info("No companies are available in this peer group.")
    st.stop()

labels = peer_data["company_id"].tolist()
benchmark_ids = peer_data.loc[peer_data["is_benchmark"], "company_id"].tolist()
selected = st.selectbox(
    "Benchmark company",
    labels,
    index=labels.index(benchmark_ids[0]) if benchmark_ids else 0,
    format_func=lambda ticker: (
        f"{company_lookup.loc[ticker, 'company_name']} ({ticker})"
        if ticker in company_lookup.index
        else ticker
    ),
)

metric_columns = {
    "ROE (%)": "roe",
    "ROCE (%)": "roce",
    "NPM (%)": "net_profit_margin_pct",
    "D/E": "debt_to_equity",
    "FCF (cr)": "free_cash_flow_cr",
    "ICR": "interest_coverage",
    "Asset turnover": "asset_turnover",
    "Dividend payout (%)": "dividend_payout_ratio_pct",
}
selected_row = peer_data[peer_data["company_id"] == selected].iloc[0]
metric_names = list(metric_columns.values())
peer_metrics = peer_data.reindex(columns=metric_names).apply(
    pd.to_numeric, errors="coerce"
)
peer_average = peer_metrics.mean()
categories = list(metric_columns)
selected_values = [
    pd.to_numeric(selected_row.get(column), errors="coerce") for column in metric_names
]
average_values = [peer_average.get(column) for column in metric_names]
figure = go.Figure()
figure.add_trace(
    go.Scatterpolar(
        r=selected_values + selected_values[:1],
        theta=categories + categories[:1],
        fill="toself",
        name=selected,
    )
)
figure.add_trace(
    go.Scatterpolar(
        r=average_values + average_values[:1],
        theta=categories + categories[:1],
        fill="toself",
        name="Peer average",
    )
)
figure.update_layout(
    polar=dict(radialaxis=dict(visible=True)),
    height=500,
    margin=dict(l=30, r=30, t=45, b=30),
)
st.plotly_chart(figure, width="stretch")

table_columns = ["company_id", "company_name", "is_benchmark", *metric_names]
table = peer_data.reindex(columns=table_columns).copy()
table = table.rename(
    columns={
        "is_benchmark": "Benchmark",
        **dict(zip(metric_columns.values(), metric_columns)),
    }
)
st.dataframe(table.round(2), width="stretch", hide_index=True)
