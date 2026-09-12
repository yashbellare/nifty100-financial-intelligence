import pandas as pd
import plotly.express as px
import streamlit as st

from src.dashboard.utils.db import get_companies, get_market_cap, get_pl, get_ratios, get_sectors


def year_number(value):
    match = pd.Series([value]).astype(str).str.extract(r"(20\d{2})").iloc[0, 0]
    return int(match) if pd.notna(match) else None


def numeric(value):
    converted = pd.to_numeric(value, errors="coerce")
    return None if pd.isna(converted) else float(converted)


def display_value(value, suffix=""):
    return "N/A" if value is None or pd.isna(value) else f"{value:,.2f}{suffix}"


def numeric_column(frame, column):
    if column not in frame:
        return pd.Series(float("nan"), index=frame.index, dtype="float64")
    return pd.to_numeric(frame[column], errors="coerce")


@st.cache_data(ttl=600)
def build_home_data(year):
    companies = get_companies().copy()
    sectors = get_sectors().copy()
    if not sectors.empty:
        companies = companies.merge(sectors[["company_id", "broad_sector", "sub_sector"]], on="company_id", how="left")

    rows = []
    for ticker in companies["company_id"].dropna().unique():
        ratios = get_ratios(ticker)
        selected_ratios = ratios.copy()
        if not selected_ratios.empty:
            selected_ratios["year_number"] = selected_ratios["year"].map(year_number)
            selected_ratios = selected_ratios[selected_ratios["year_number"] == year].tail(1)

        market_cap = get_market_cap(ticker, year)
        selected_market_cap = market_cap.tail(1) if not market_cap.empty else pd.DataFrame()
        pl = get_pl(ticker).copy()
        if not pl.empty:
            pl["year_number"] = pl["year"].map(year_number)
        current = pl[pl["year_number"] == year].tail(1) if not pl.empty else pd.DataFrame()
        previous = pl[pl["year_number"] == year - 5].tail(1) if not pl.empty else pd.DataFrame()

        row = {"company_id": ticker}
        if not selected_ratios.empty:
            row.update(selected_ratios.iloc[0].to_dict())
        if not selected_market_cap.empty:
            row.update(selected_market_cap.iloc[0].to_dict())
        if not current.empty and not previous.empty:
            sales_now = numeric(current.iloc[0].get("sales"))
            sales_then = numeric(previous.iloc[0].get("sales"))
            if sales_now is not None and sales_then and sales_then > 0:
                row["revenue_cagr_5yr_calculated"] = ((sales_now / sales_then) ** 0.2 - 1) * 100
        rows.append(row)

    metrics = pd.DataFrame(rows)
    return companies.merge(metrics, on="company_id", how="left", suffixes=("", "_metric"))


st.sidebar.header("Dashboard filters")
year = st.sidebar.selectbox("Select year", list(range(2019, 2025)), index=5)
dashboard_df = build_home_data(year)

if dashboard_df.empty:
    st.error("No company data is available.")
    st.stop()

roe = numeric_column(dashboard_df, "return_on_equity_pct")
pe = numeric_column(dashboard_df, "pe_ratio")
de = numeric_column(dashboard_df, "debt_to_equity")
revenue_cagr = numeric_column(dashboard_df, "revenue_cagr_5yr").combine_first(
    numeric_column(dashboard_df, "revenue_cagr_5yr_calculated")
)

st.title("Nifty 100 Analytics")
st.caption(f"Financial overview of Nifty 100 companies - FY {year}")

kpis = st.columns(6)
kpis[0].metric("Average ROE", display_value(roe.mean(), "%"))
kpis[1].metric("Median P/E", display_value(pe.median()))
kpis[2].metric("Median D/E", display_value(de.median()))
kpis[3].metric("Total companies", f"{dashboard_df['company_id'].nunique()}")
kpis[4].metric("Median revenue CAGR 5Y", display_value(revenue_cagr.median(), "%"))
kpis[5].metric("Debt-free companies", f"{int((de == 0).sum())}")

st.divider()
left, right = st.columns(2)
with left:
    st.subheader("Sector breakdown")
    sector_data = dashboard_df.assign(Sector=dashboard_df["broad_sector"].fillna("Unknown")).groupby("Sector", as_index=False)["company_id"].nunique().rename(columns={"company_id": "Companies"})
    figure = px.pie(sector_data, names="Sector", values="Companies", hole=0.55)
    figure.update_layout(height=430, margin=dict(l=10, r=10, t=30, b=10))
    st.plotly_chart(figure, width="stretch")

with right:
    st.subheader("Top 5 companies by composite quality score")
    quality = dashboard_df.copy()
    if "composite_quality_score" in quality:
        quality["composite_score"] = pd.to_numeric(quality["composite_quality_score"], errors="coerce")
    else:
        components = []
        for column in ["return_on_equity_pct", "net_profit_margin_pct", "interest_coverage"]:
            if column in quality:
                components.append(pd.to_numeric(quality[column], errors="coerce").rank(pct=True))
        if "debt_to_equity" in quality:
            components.append(pd.to_numeric(quality["debt_to_equity"], errors="coerce").rank(pct=True, ascending=False))
        quality["composite_score"] = pd.concat(components, axis=1).mean(axis=1).mul(100) if components else pd.NA
    columns = [column for column in ["company_id", "company_name", "broad_sector", "composite_score"] if column in quality]
    top5 = quality.nlargest(5, "composite_score")[columns].copy()
    if "composite_score" in top5:
        top5["composite_score"] = pd.to_numeric(top5["composite_score"], errors="coerce").round(2)
    st.dataframe(top5.reset_index(drop=True), width="stretch", hide_index=True)

with st.expander("Data availability"):
    ratio_count = numeric_column(dashboard_df, "return_on_equity_pct").notna().sum()
    st.write(f"Companies loaded: **{dashboard_df['company_id'].nunique()}**")
    st.write(f"Companies with ratio data for {year}: **{ratio_count}**")
