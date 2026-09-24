import re

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from src.dashboard.utils.db import (
    get_bs,
    get_cf,
    get_companies,
    get_pl,
    get_pros_cons,
    get_ratios,
    get_sectors,
)


def year_number(value):
    """Extract a calendar year from a source period."""
    match = re.search(r"20\d{2}", str(value))
    return int(match.group()) if match else None


def number(value):
    """Convert a value to float or return None."""
    converted = pd.to_numeric(value, errors="coerce")
    return None if pd.isna(converted) else float(converted)


def format_metric(value, suffix=""):
    """Format a profile metric for display."""
    return "N/A" if value is None or pd.isna(value) else f"{value:,.2f}{suffix}"


def latest_row(frame):
    """Return the latest valid year row from a dataframe."""
    if frame.empty or "year" not in frame:
        return pd.Series(dtype="object")
    result = frame.copy()
    result["year_number"] = result["year"].map(year_number)
    result = result.dropna(subset=["year_number"])
    return (
        result.sort_values("year_number").iloc[-1]
        if not result.empty
        else pd.Series(dtype="object")
    )


def split_items(value):
    """Split a semicolon or newline-delimited text field."""
    if value is None or pd.isna(value):
        return []
    return [item.strip() for item in re.split(r"[;|\n]+", str(value)) if item.strip()]


companies = get_companies().copy()
sectors = get_sectors().copy()
if not sectors.empty:
    companies = companies.merge(sectors, on="company_id", how="left")

st.title("Company profile")
search = st.text_input(
    "Search by company name or ticker", placeholder="Type a company name or ticker"
)
search_text = search.strip().lower()
if search_text:
    matches = companies[
        companies["company_id"]
        .astype(str)
        .str.lower()
        .str.contains(search_text, na=False)
        | companies["company_name"]
        .astype(str)
        .str.lower()
        .str.contains(search_text, na=False)
    ]
else:
    matches = companies

if matches.empty:
    st.warning("Ticker not found - please try another")
    st.stop()

options = matches["company_id"].tolist()
labels = {
    row.company_id: f"{row.company_name} ({row.company_id})"
    for row in matches.itertuples()
}
ticker = st.selectbox(
    "Select company", options, format_func=lambda value: labels.get(value, value)
)
company = companies[companies["company_id"] == ticker].iloc[0]

pl = get_pl(ticker).copy()
bs = get_bs(ticker).copy()
ratios = get_ratios(ticker).copy()
cashflow = get_cf(ticker).copy()
for frame in [pl, bs, ratios, cashflow]:
    if not frame.empty and "year" in frame:
        frame["year_number"] = frame["year"].map(year_number)

latest_pl = latest_row(pl)
latest_bs = latest_row(bs)
latest_ratios = latest_row(ratios)

roe = number(latest_ratios.get("return_on_equity_pct"))
if roe is None:
    roe = number(company.get("roe_percentage"))
roce = number(company.get("roce_percentage"))
if latest_pl.get("operating_profit") is not None and not latest_bs.empty:
    capital = sum(
        number(latest_bs.get(column)) or 0
        for column in ["equity_capital", "reserves", "borrowings"]
    )
    ebit = number(latest_pl.get("operating_profit"))
    if capital > 0 and ebit is not None:
        roce = ebit / capital * 100

st.subheader(str(company.get("company_name", ticker)))
st.caption(
    f"{ticker} | {company.get('broad_sector', 'N/A')} | {company.get('sub_sector', 'N/A')}"
)
st.write(company.get("about_company") or "About information is not available.")

kpis = st.columns(6)
kpis[0].metric("ROE", format_metric(roe, "%"))
kpis[1].metric("ROCE", format_metric(roce, "%"))
kpis[2].metric(
    "Net profit margin",
    format_metric(number(latest_ratios.get("net_profit_margin_pct")), "%"),
)
kpis[3].metric("D/E", format_metric(number(latest_ratios.get("debt_to_equity"))))
kpis[4].metric(
    "Revenue CAGR 5Y", format_metric(number(latest_ratios.get("revenue_cagr_5yr")), "%")
)
kpis[5].metric(
    "FCF", format_metric(number(latest_ratios.get("free_cash_flow_cr")), " cr")
)

if pl.empty:
    st.info("Financial history is not available for this company.")
else:
    chart_data = (
        pl[["year_number", "sales", "net_profit"]]
        .dropna(subset=["year_number"])
        .sort_values("year_number")
        .tail(10)
    )
    chart_data[["sales", "net_profit"]] = chart_data[["sales", "net_profit"]].apply(
        pd.to_numeric, errors="coerce"
    )
    chart_data = chart_data.dropna(subset=["sales", "net_profit"], how="all")
    if chart_data.empty:
        st.info("No chartable financial history is available for this company.")
        st.stop()
    chart_data = chart_data.rename(
        columns={"year_number": "Year", "sales": "Revenue", "net_profit": "Net profit"}
    )
    bar = go.Figure()
    bar.add_bar(x=chart_data["Year"], y=chart_data["Revenue"], name="Revenue")
    bar.add_bar(x=chart_data["Year"], y=chart_data["Net profit"], name="Net profit")
    bar.update_layout(
        barmode="group",
        height=400,
        margin=dict(l=10, r=10, t=30, b=10),
        yaxis_title="INR crore",
    )
    st.plotly_chart(bar, width="stretch")

    trend = []
    for _, row in chart_data.iterrows():
        balance = (
            bs[bs["year_number"] == row["Year"]].tail(1)
            if not bs.empty
            else pd.DataFrame()
        )
        capital = (
            0
            if balance.empty
            else sum(
                number(balance.iloc[0].get(column)) or 0
                for column in ["equity_capital", "reserves", "borrowings"]
            )
        )
        source_pl = pl[pl["year_number"] == row["Year"]].tail(1)
        roce_value = None
        if not source_pl.empty and capital > 0:
            roce_value = (
                (number(source_pl.iloc[0].get("operating_profit")) or 0) / capital * 100
            )
        ratio = (
            ratios[ratios["year_number"] == row["Year"]].tail(1)
            if not ratios.empty
            else pd.DataFrame()
        )
        trend.append(
            {
                "Year": row["Year"],
                "ROE": (
                    number(ratio.iloc[0].get("return_on_equity_pct"))
                    if not ratio.empty
                    else None
                ),
                "ROCE": roce_value,
            }
        )
    trend_data = pd.DataFrame(trend)
    line = make_subplots(specs=[[{"secondary_y": True}]])
    line.add_trace(
        go.Scatter(
            x=trend_data["Year"], y=trend_data["ROE"], name="ROE", mode="lines+markers"
        ),
        secondary_y=False,
    )
    line.add_trace(
        go.Scatter(
            x=trend_data["Year"],
            y=trend_data["ROCE"],
            name="ROCE",
            mode="lines+markers",
        ),
        secondary_y=True,
    )
    line.update_layout(height=400, margin=dict(l=10, r=10, t=30, b=10))
    line.update_yaxes(title_text="ROE (%)", secondary_y=False)
    line.update_yaxes(title_text="ROCE (%)", secondary_y=True)
    st.plotly_chart(line, width="stretch")

pros_cons = get_pros_cons(ticker)
if not pros_cons.empty:
    row = pros_cons.iloc[0]
    pros, cons = st.columns(2)
    with pros:
        st.subheader("Pros")
        for item in split_items(row.get("pros")):
            st.success(item, icon=":material/check_circle:")
    with cons:
        st.subheader("Cons")
        for item in split_items(row.get("cons")):
            st.error(item, icon=":material/cancel:")
