from pathlib import Path

import pandas as pd
import streamlit as st


# Project paths
PROJECT_ROOT = Path(__file__).resolve().parents[3]

RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
SUPPORTING_DATA_DIR = PROJECT_ROOT / "data" / "supporting"
OUTPUT_DIR = PROJECT_ROOT / "output"


def _load_excel(filename: str, header: int = 1, supporting: bool = False):
    """Load an Excel file from the correct project data directory."""

    data_dir = SUPPORTING_DATA_DIR if supporting else RAW_DATA_DIR
    path = data_dir / filename

    if not path.exists():
        raise FileNotFoundError(f"Data file not found: {path}")

    return pd.read_excel(path, header=header)


def _filter_company(df: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """Safely filter a dataframe by company ticker."""

    if "company_id" not in df.columns:
        return df.iloc[0:0].copy()

    ticker = str(ticker).strip().upper()

    return df[
        df["company_id"]
        .astype(str)
        .str.strip()
        .str.upper()
        == ticker
    ].copy()


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Keep source variations usable by every dashboard page."""
    result = df.copy()
    result.columns = [str(column).strip() for column in result.columns]
    if "company_id" in result.columns and "id" in result.columns:
        result = result.drop(columns=["id"])
    aliases = {
        "id": "company_id",
        "Year": "year",
        "Annual_Report": "annual_report",
        "broad sector": "broad_sector",
        "sub sector": "sub_sector",
        "dividend_yield": "dividend_yield_pct",
    }
    result = result.rename(columns={key: value for key, value in aliases.items() if key in result.columns})
    return result


# ============================================================
# COMPANY MASTER
# ============================================================

@st.cache_data(ttl=600)
def get_companies() -> pd.DataFrame:
    return _normalize_columns(_load_excel("companies.xlsx", header=1))


# ============================================================
# FINANCIAL RATIOS
# ============================================================

@st.cache_data(ttl=600)
def get_ratios(ticker: str, year=None) -> pd.DataFrame:
    df = _load_excel(
        "financial_ratios.xlsx",
        header=0,
        supporting=True,
    )

    df = _filter_company(_normalize_columns(df), ticker)

    if year is not None and "year" in df.columns:
        df = df[
            df["year"]
            .astype(str)
            .str.contains(str(year), case=False, na=False)
        ].copy()

    return df


# ============================================================
# PROFIT & LOSS
# ============================================================

@st.cache_data(ttl=600)
def get_pl(ticker: str) -> pd.DataFrame:
    df = _load_excel("profitandloss.xlsx", header=1)

    return _filter_company(_normalize_columns(df), ticker)


# ============================================================
# BALANCE SHEET
# ============================================================

@st.cache_data(ttl=600)
def get_bs(ticker: str) -> pd.DataFrame:
    df = _load_excel("balancesheet.xlsx", header=1)

    return _filter_company(_normalize_columns(df), ticker)


# ============================================================
# CASH FLOW
# ============================================================

@st.cache_data(ttl=600)
def get_cf(ticker: str) -> pd.DataFrame:
    df = _load_excel("cashflow.xlsx", header=1)

    return _filter_company(_normalize_columns(df), ticker)


# ============================================================
# SECTORS
# ============================================================

@st.cache_data(ttl=600)
def get_sectors() -> pd.DataFrame:
    return _normalize_columns(_load_excel(
        "sectors.xlsx",
        header=0,
        supporting=True,
    ))


# ============================================================
# PEER GROUPS
# ============================================================

@st.cache_data(ttl=600)
def get_peers(group_name: str) -> pd.DataFrame:
    df = _normalize_columns(_load_excel(
        "peer_groups.xlsx",
        header=0,
        supporting=True,
    ))

    if "peer_group_name" not in df.columns:
        return df.iloc[0:0].copy()

    group = str(group_name).strip().lower()

    return df[
        df["peer_group_name"]
        .astype(str)
        .str.strip()
        .str.lower()
        == group
    ].copy()


@st.cache_data(ttl=600)
def get_peer_group_names() -> list[str]:
    """Return the distinct peer groups available to the dashboard."""

    df = _load_excel("peer_groups.xlsx", header=0, supporting=True)
    if "peer_group_name" not in df.columns:
        return []
    return sorted(df["peer_group_name"].dropna().astype(str).str.strip().unique().tolist())


# ============================================================
# VALUATION
# ============================================================

@st.cache_data(ttl=600)
def get_valuation(ticker: str) -> pd.DataFrame:
    path = OUTPUT_DIR / "valuation_summary.xlsx"

    if not path.exists():
        return pd.DataFrame()

    df = pd.read_excel(path)

    return _filter_company(df, ticker)


# ============================================================
# MARKET CAP
# ============================================================

@st.cache_data(ttl=600)
def get_market_cap(ticker: str, year=None) -> pd.DataFrame:
    df = _normalize_columns(_load_excel(
        "market_cap.xlsx",
        header=0,
        supporting=True,
    ))

    df = _filter_company(df, ticker)

    if year is not None and "year" in df.columns:
        df = df[
            df["year"].astype(str).str.extract(r"(20\d{2})", expand=False)
            == str(year)
        ].copy()

    return df


# ============================================================
# ANNUAL REPORT DOCUMENTS
# ============================================================

@st.cache_data(ttl=600)
def get_documents(ticker: str) -> pd.DataFrame:
    df = _load_excel("documents.xlsx", header=1)

    return _filter_company(_normalize_columns(df), ticker)


# ============================================================
# PROS & CONS
# ============================================================

@st.cache_data(ttl=600)
def get_pros_cons(ticker: str) -> pd.DataFrame:
    df = _load_excel("prosandcons.xlsx", header=1)

    return _filter_company(_normalize_columns(df), ticker)


# ============================================================
# STOCK PRICES
# ============================================================

@st.cache_data(ttl=600)
def get_stock_prices(ticker: str) -> pd.DataFrame:
    df = _normalize_columns(_load_excel(
        "stock_prices.xlsx",
        header=0,
        supporting=True,
    ))

    return _filter_company(df, ticker)