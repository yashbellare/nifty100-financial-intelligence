import streamlit as st
import pandas as pd
import plotly.express as px

from src.dashboard.utils.db import (
    get_companies,
    get_ratios,
    get_sectors,
)


# ---------------------------------------------------------
# HELPERS
# ---------------------------------------------------------
def safe_median(series):
    """Return median safely, ignoring missing values."""
    series = pd.to_numeric(series, errors="coerce").dropna()

    if series.empty:
        return None

    return series.median()


def safe_mean(series):
    """Return mean safely, ignoring missing values."""
    series = pd.to_numeric(series, errors="coerce").dropna()

    if series.empty:
        return None

    return series.mean()


def fmt(value, suffix=""):
    """Format KPI values safely."""
    if value is None or pd.isna(value):
        return "N/A"

    return f"{value:,.2f}{suffix}"


# ---------------------------------------------------------
# LOAD DATA
# ---------------------------------------------------------
companies = get_companies().copy()

if companies.empty:
    st.error("No company data is available.")
    st.stop()


# ---------------------------------------------------------
# YEAR SELECTOR
# ---------------------------------------------------------
st.sidebar.header("Dashboard Filters")

year = st.sidebar.selectbox(
    "Select Year",
    list(range(2019, 2025)),
    index=5,
)


# ---------------------------------------------------------
# LOAD RATIOS FOR SELECTED YEAR
# ---------------------------------------------------------
ratio_frames = []

for ticker in companies["company_id"].dropna().unique():
    try:
        df = get_ratios(ticker)

        if df is not None and not df.empty:
            df = df.copy()

            if "year" in df.columns:
                df["year"] = pd.to_numeric(
                    df["year"],
                    errors="coerce",
                )

                selected = df[df["year"] == year]

                if not selected.empty:
                    ratio_frames.append(selected.iloc[-1])

    except Exception:
        continue


if ratio_frames:
    ratios = pd.DataFrame(ratio_frames)

    # Keep one row per company
    ratios = ratios.drop_duplicates(
        subset=["company_id"],
        keep="last",
    )
else:
    ratios = pd.DataFrame()


# ---------------------------------------------------------
# MERGE COMPANY + RATIO DATA
# ---------------------------------------------------------
if not ratios.empty:
    dashboard_df = companies.merge(
        ratios,
        on="company_id",
        how="left",
        suffixes=("", "_ratio"),
    )
else:
    dashboard_df = companies.copy()


# ---------------------------------------------------------
# TITLE
# ---------------------------------------------------------
st.title("Nifty 100 Analytics")
st.caption(
    f"Financial overview of Nifty 100 companies — FY {year}"
)


# ---------------------------------------------------------
# KPI CALCULATIONS
# ---------------------------------------------------------

# ROE
if "return_on_equity_pct" in dashboard_df.columns:
    avg_roe = safe_mean(
        dashboard_df["return_on_equity_pct"]
    )
elif "roe_percentage" in dashboard_df.columns:
    avg_roe = safe_mean(
        dashboard_df["roe_percentage"]
    )
else:
    avg_roe = None


# P/E
pe_column = None

for column in ["pe_ratio", "pe", "price_to_earnings"]:
    if column in dashboard_df.columns:
        pe_column = column
        break

median_pe = (
    safe_median(dashboard_df[pe_column])
    if pe_column
    else None
)


# D/E
if "debt_to_equity" in dashboard_df.columns:
    median_de = safe_median(
        dashboard_df["debt_to_equity"]
    )
else:
    median_de = None


# Total companies
total_companies = dashboard_df["company_id"].nunique()


# ---------------------------------------------------------
# REVENUE CAGR
# ---------------------------------------------------------
median_revenue_cagr = None

try:
    cagr_values = []

    for ticker in companies["company_id"].dropna().unique():
        try:
            pl = get_ratios(ticker)

            if pl is None or pl.empty:
                continue

            pl = pl.copy()

            if "year" not in pl.columns:
                continue

            pl["year"] = pd.to_numeric(
                pl["year"],
                errors="coerce",
            )

            # Need current year and five years earlier
            current = pl[pl["year"] == year]

            previous = pl[
                pl["year"] == year - 5
            ]

            if current.empty or previous.empty:
                continue

            current_fcf = current.iloc[-1].get(
                "free_cash_flow_cr"
            )

            previous_fcf = previous.iloc[-1].get(
                "free_cash_flow_cr"
            )

        except Exception:
            continue

    # Revenue CAGR is calculated below using PL data
    # because revenue/sales are stored in the P&L table.

except Exception:
    pass


# ---------------------------------------------------------
# CALCULATE REVENUE CAGR FROM P&L
# ---------------------------------------------------------
try:
    from src.dashboard.utils.db import get_pl

    cagr_values = []

    for ticker in companies["company_id"].dropna().unique():

        try:
            pl = get_pl(ticker)

            if pl is None or pl.empty:
                continue

            pl = pl.copy()

            pl["year"] = pd.to_numeric(
                pl["year"],
                errors="coerce",
            )

            current = pl[pl["year"] == year]
            previous = pl[pl["year"] == year - 5]

            if current.empty or previous.empty:
                continue

            current_sales = pd.to_numeric(
                current.iloc[-1]["sales"],
                errors="coerce",
            )

            previous_sales = pd.to_numeric(
                previous.iloc[-1]["sales"],
                errors="coerce",
            )

            if (
                pd.isna(current_sales)
                or pd.isna(previous_sales)
                or previous_sales <= 0
                or current_sales < 0
            ):
                continue

            cagr = (
                (current_sales / previous_sales) ** (1 / 5)
                - 1
            ) * 100

            cagr_values.append(cagr)

        except Exception:
            continue

    if cagr_values:
        median_revenue_cagr = pd.Series(
            cagr_values
        ).median()

except Exception:
    median_revenue_cagr = None


# ---------------------------------------------------------
# DEBT-FREE COUNT
# ---------------------------------------------------------
debt_free_count = "N/A"

if "debt_to_equity" in dashboard_df.columns:

    de_values = pd.to_numeric(
        dashboard_df["debt_to_equity"],
        errors="coerce",
    )

    debt_free_count = int(
        (de_values.fillna(999) == 0).sum()
    )


# ---------------------------------------------------------
# KPI TILES
# ---------------------------------------------------------
k1, k2, k3, k4, k5, k6 = st.columns(6)

with k1:
    st.metric(
        "Average ROE",
        fmt(avg_roe, "%"),
    )

with k2:
    st.metric(
        "Median P/E",
        fmt(median_pe),
    )

with k3:
    st.metric(
        "Median D/E",
        fmt(median_de),
    )

with k4:
    st.metric(
        "Total Companies",
        f"{total_companies}",
    )

with k5:
    st.metric(
        "Median Revenue CAGR 5Y",
        fmt(median_revenue_cagr, "%"),
    )

with k6:
    st.metric(
        "Debt-Free Companies",
        str(debt_free_count),
    )


st.divider()


# ---------------------------------------------------------
# SECTOR BREAKDOWN
# ---------------------------------------------------------
st.subheader("Sector Breakdown")

sector_column = None

for column in [
    "sector",
    "broad_sector",
    "sector_name",
]:
    if column in dashboard_df.columns:
        sector_column = column
        break


if sector_column:

    sector_data = (
        dashboard_df[sector_column]
        .fillna("Unknown")
        .value_counts()
        .reset_index()
    )

    sector_data.columns = [
        "Sector",
        "Companies",
    ]

    fig = px.pie(
        sector_data,
        names="Sector",
        values="Companies",
        hole=0.55,
        title=f"Companies by Sector — {year}",
    )

    fig.update_layout(
        height=500,
        margin=dict(l=20, r=20, t=60, b=20),
    )

    st.plotly_chart(
        fig,
        width="stretch",
    )

else:
    st.info(
        "Sector information is not available in the company dataset."
    )


# ---------------------------------------------------------
# TOP 5 COMPANIES
# ---------------------------------------------------------
st.subheader("Top 5 Companies by Quality Metrics")


quality_df = dashboard_df.copy()


# Try to build a simple composite quality score
quality_components = []


if "return_on_equity_pct" in quality_df.columns:
    quality_components.append(
        pd.to_numeric(
            quality_df["return_on_equity_pct"],
            errors="coerce",
        ).rank(pct=True)
    )

elif "roe_percentage" in quality_df.columns:
    quality_components.append(
        pd.to_numeric(
            quality_df["roe_percentage"],
            errors="coerce",
        ).rank(pct=True)
    )


if "net_profit_margin_pct" in quality_df.columns:
    quality_components.append(
        pd.to_numeric(
            quality_df["net_profit_margin_pct"],
            errors="coerce",
        ).rank(pct=True)
    )


if "interest_coverage" in quality_df.columns:
    quality_components.append(
        pd.to_numeric(
            quality_df["interest_coverage"],
            errors="coerce",
        ).rank(pct=True)
    )


if "debt_to_equity" in quality_df.columns:

    de_rank = pd.to_numeric(
        quality_df["debt_to_equity"],
        errors="coerce",
    ).rank(
        pct=True,
        ascending=False,
    )

    quality_components.append(de_rank)


if quality_components:

    quality_df["composite_score"] = (
        pd.concat(
            quality_components,
            axis=1,
        ).mean(axis=1)
        * 100
    )

    top5 = (
        quality_df
        .sort_values(
            "composite_score",
            ascending=False,
        )
        .head(5)
    )

    display_columns = [
        "company_id",
    ]

    if "company_name" in top5.columns:
        display_columns.append("company_name")

    if sector_column:
        display_columns.append(sector_column)

    display_columns.append("composite_score")

    top5_display = top5[display_columns].copy()

    top5_display["composite_score"] = (
        top5_display["composite_score"]
        .round(2)
    )

    top5_display = top5_display.reset_index(drop=True)

    top5_display.index += 1

    st.dataframe(
        top5_display,
        width="stretch",
    )

else:
    st.info(
        "Not enough metrics available to calculate a quality score."
    )


# ---------------------------------------------------------
# DATA AVAILABILITY
# ---------------------------------------------------------
with st.expander("Data Availability"):

    st.write(
        f"Companies loaded: **{total_companies}**"
    )

    if not ratios.empty:
        st.write(
            f"Companies with ratio data for {year}: "
            f"**{ratios['company_id'].nunique()}**"
        )
    else:
        st.write(
            f"No ratio data found for {year}."
        )