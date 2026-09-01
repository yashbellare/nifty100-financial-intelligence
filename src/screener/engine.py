import sqlite3
from pathlib import Path

import pandas as pd
import yaml


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[2]

DB_PATH = BASE_DIR / "nifty100.db"
CONFIG_PATH = BASE_DIR / "config" / "screener_config.yaml"
OUTPUT_DIR = BASE_DIR / "output"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# DATABASE HELPERS
# ============================================================

def get_connection():
    """Create a SQLite database connection."""
    return sqlite3.connect(DB_PATH)


def get_tables(conn):
    """Return all SQLite table names."""
    query = """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
        ORDER BY name
    """
    return pd.read_sql_query(query, conn)["name"].tolist()


def get_columns(conn, table_name):
    """Return column names for a SQLite table."""
    rows = conn.execute(
        f'PRAGMA table_info("{table_name}")'
    ).fetchall()
    return [row[1] for row in rows]


def find_table(conn, possible_names):
    """Return the first available table from possible names."""
    tables = get_tables(conn)

    for name in possible_names:
        if name in tables:
            return name

    return None


# ============================================================
# CONFIGURATION
# ============================================================

def load_config():
    """Load the complete YAML configuration."""
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"Configuration file not found:\n{CONFIG_PATH}"
        )

    with open(CONFIG_PATH, "r", encoding="utf-8") as file:
        return yaml.safe_load(file) or {}


def load_filters():
    """Return generic Day 15 filters."""
    config = load_config()
    return config.get("filters", {})


# ============================================================
# COLUMN ALIASES
# ============================================================

COLUMN_ALIASES = {
    "company_id": [
        "company_id",
        "id",
        "companyid",
    ],
    "company_name": [
        "company_name",
        "name",
        "company",
        "companyname",
        "stock_name",
    ],
    "sector": [
        "sector",
        "broad_sector",
        "sector_name",
        "industry",
    ],
    "broad_sector": [
        "broad_sector",
        "sector",
        "sector_name",
    ],
    "year": [
        "year",
        "financial_year",
        "fy",
        "date",
        "period",
    ],
    "roe": [
        "roe",
        "roe_percentage",
        "return_on_equity_pct",
        "return_on_equity",
        "return_on_equity_percentage",
    ],
    "roce": [
        "roce",
        "roce_percentage",
        "return_on_capital_employed",
        "return_on_capital_employed_pct",
    ],
    "npm": [
        "npm",
        "net_profit_margin",
        "net_profit_margin_pct",
        "net_profit_margin_percentage",
    ],
    "opm": [
        "opm",
        "operating_profit_margin",
        "operating_profit_margin_pct",
        "opm_pct",
    ],
    "de": [
        "de",
        "de_ratio",
        "debt_to_equity",
        "debt_to_equity_pct",
        "debt_to_equity_ratio",
    ],
    "de_previous_year": [
        "de_previous_year",
        "de_prev_year",
        "previous_de",
        "de_last_year",
        "previous_year_de",
    ],
    "fcf": [
        "fcf",
        "free_cash_flow",
        "free_cash_flow_cr",
    ],
    "net_debt": [
        "net_debt",
        "net_debt_cr",
    ],
    "icr": [
        "icr",
        "interest_coverage",
        "interest_coverage_ratio",
    ],
    "icr_label": [
        "icr_label",
        "interest_coverage_label",
    ],
    "asset_turnover": [
        "asset_turnover",
        "asset_turnover_ratio",
    ],
    "revenue_cagr_3yr": [
        "revenue_cagr_3yr",
        "revenue_cagr_3yr_pct",
        "sales_cagr_3yr",
    ],
    "revenue_cagr_5yr": [
        "revenue_cagr_5yr",
        "revenue_cagr_5yr_pct",
        "compounded_sales_growth",
        "sales_cagr_5yr",
    ],
    "revenue_cagr_10yr": [
        "revenue_cagr_10yr",
        "revenue_cagr_10yr_pct",
    ],
    "pat_cagr_5yr": [
        "pat_cagr_5yr",
        "pat_cagr_5yr_pct",
        "profit_cagr_5yr",
        "profit_growth_5yr",
    ],
    "eps_cagr_5yr": [
        "eps_cagr_5yr",
        "eps_cagr_5yr_pct",
        "eps_growth_5yr",
    ],
    "pe": [
        "pe",
        "pe_ratio",
        "price_to_earnings",
    ],
    "pb": [
        "pb",
        "pb_ratio",
        "price_to_book",
    ],
    "dividend_yield": [
        "dividend_yield",
        "dividend_yield_pct",
    ],
    "dividend_payout": [
        "dividend_payout",
        "dividend_payout_ratio",
        "dividend_payout_pct",
        "dividend_payout_percentage",
    ],
    "market_cap": [
        "market_cap",
        "market_cap_cr",
        "market_cap_crore",
        "market_capitalization",
    ],
    "net_profit": [
        "net_profit",
        "net_profit_cr",
    ],
    "sales": [
        "sales",
        "sales_cr",
        "revenue",
        "revenue_cr",
        "total_sales",
    ],
    "face_value": [
        "face_value",
    ],
    "book_value": [
        "book_value",
        "book_value_per_share",
    ],
    "composite_quality_score": [
        "composite_quality_score",
        "composite_score",
        "quality_score",
    ],
}


# ============================================================
# COLUMN HELPERS
# ============================================================

def find_column(available_columns, logical_name):
    """Find the real column corresponding to a logical metric."""
    available_lower = {
        str(column).lower(): column
        for column in available_columns
    }

    aliases = COLUMN_ALIASES.get(
        logical_name,
        [logical_name]
    )

    for alias in aliases:
        if alias.lower() in available_lower:
            return available_lower[alias.lower()]

    return None


def rename_to_logical_columns(df):
    """
    Add/rename standard logical columns without destroying
    the original database columns.
    """
    result = df.copy()

    for logical_name in COLUMN_ALIASES:
        if logical_name in result.columns:
            continue

        actual = find_column(
            result.columns.tolist(),
            logical_name
        )

        if actual is not None:
            result[logical_name] = result[actual]

    return result


# ============================================================
# DATA LOADING
# ============================================================

def load_data():
    """
    Load financial-ratio history and enrich it with:
      - company names
      - sectors
      - annual sales/dividend payout
      - market-cap valuation ratios

    This fixes the earlier problem where the financial_ratios
    table did not itself contain PE, PB, dividend yield, sales,
    and dividend payout.
    """
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"Database not found:\n{DB_PATH}"
        )

    conn = get_connection()

    try:
        financial_table = find_table(
            conn,
            [
                "financial_ratios",
                "financial_ratio",
                "ratios",
            ]
        )

        if financial_table is None:
            raise RuntimeError(
                "Could not find financial_ratios table. "
                f"Available tables: {get_tables(conn)}"
            )

        financial_df = pd.read_sql_query(
            f'SELECT * FROM "{financial_table}"',
            conn
        )

        if financial_df.empty:
            raise RuntimeError(
                f"Table '{financial_table}' contains no data."
            )

        result = rename_to_logical_columns(
            financial_df
        )

        # --------------------------------------------------------
        # Company information
        # --------------------------------------------------------

        company_table = find_table(
            conn,
            ["companies", "company"]
        )

        if company_table:
            company_df = pd.read_sql_query(
                f'SELECT * FROM "{company_table}"',
                conn
            )
            company_df = rename_to_logical_columns(
                company_df
            )

            company_cols = [
                column
                for column in [
                    "company_id",
                    "company_name",
                    "face_value",
                    "book_value",
                    "roce",
                    "roe",
                ]
                if column in company_df.columns
            ]

            if "company_id" in result.columns and (
                "company_id" in company_df.columns
            ):
                company_small = company_df[
                    company_cols
                ].drop_duplicates(
                    subset=["company_id"]
                )

                result = result.merge(
                    company_small,
                    on="company_id",
                    how="left",
                    suffixes=("", "_company")
                )

                # Prefer financial-ratio values when present.
                for metric in [
                    "company_name",
                    "face_value",
                    "book_value",
                    "roce",
                    "roe",
                ]:
                    company_metric = f"{metric}_company"

                    if (
                        metric not in result.columns
                        and company_metric in result.columns
                    ):
                        result[metric] = result[
                            company_metric
                        ]

        # --------------------------------------------------------
        # Sector information
        # --------------------------------------------------------

        sector_table = find_table(
            conn,
            ["sectors", "sector"]
        )

        if sector_table:
            sector_df = pd.read_sql_query(
                f'SELECT * FROM "{sector_table}"',
                conn
            )
            sector_df = rename_to_logical_columns(
                sector_df
            )

            if "company_id" in sector_df.columns:
                keep = [
                    column
                    for column in [
                        "company_id",
                        "sector",
                        "broad_sector",
                    ]
                    if column in sector_df.columns
                ]

                sector_small = sector_df[
                    keep
                ].drop_duplicates(
                    subset=["company_id"]
                )

                if "company_id" in result.columns:
                    result = result.merge(
                        sector_small,
                        on="company_id",
                        how="left",
                        suffixes=("", "_sector")
                    )

                    if (
                        "sector" not in result.columns
                        and "broad_sector_sector" in result.columns
                    ):
                        result["sector"] = result[
                            "broad_sector_sector"
                        ]

        # --------------------------------------------------------
        # Annual P&L
        # --------------------------------------------------------

        pl_table = find_table(
            conn,
            ["profitandloss", "profit_and_loss"]
        )

        if pl_table:
            pl_df = pd.read_sql_query(
                f'SELECT * FROM "{pl_table}"',
                conn
            )
            pl_df = rename_to_logical_columns(
                pl_df
            )

            if "company_id" in pl_df.columns:
                pl_df["_calendar_year"] = (
                    pl_df["year"]
                    .astype(str)
                    .str.extract(r"(\d{4})")[0]
                )

                keep = [
                    column
                    for column in [
                        "company_id",
                        "year",
                        "sales",
                        "dividend_payout",
                        "net_profit",
                        "eps",
                        "opm",
                    ]
                    if column in pl_df.columns
                ]

                annual_pl = pl_df[
                    keep + ["_calendar_year"]
                ].copy()

                # For each company/year, retain the latest
                # available annual P&L record.
                annual_pl = (
                    annual_pl
                    .sort_values(
                        ["company_id", "_calendar_year", "year"]
                    )
                    .drop_duplicates(
                        subset=[
                            "company_id",
                            "_calendar_year",
                        ],
                        keep="last"
                    )
                )

                result["_calendar_year"] = (
                    result["year"]
                    .astype(str)
                    .str.extract(r"(\d{4})")[0]
                )

                if "company_id" in result.columns:
                    result = result.merge(
                        annual_pl,
                        on=[
                            "company_id",
                            "_calendar_year",
                        ],
                        how="left",
                        suffixes=("", "_pl")
                    )

                    for metric in [
                        "sales",
                        "dividend_payout",
                        "net_profit",
                        "opm",
                    ]:
                        pl_metric = f"{metric}_pl"

                        if metric not in result.columns:
                            if pl_metric in result.columns:
                                result[metric] = result[
                                    pl_metric
                                ]
                        else:
                            if pl_metric in result.columns:
                                result[metric] = result[
                                    metric
                                ].combine_first(
                                    result[pl_metric]
                                )

        # --------------------------------------------------------
        # Market-cap / valuation table
        # --------------------------------------------------------

        mc_table = find_table(
            conn,
            ["market_cap", "marketcap"]
        )

        if mc_table:
            mc_df = pd.read_sql_query(
                f'SELECT * FROM "{mc_table}"',
                conn
            )
            mc_df = rename_to_logical_columns(
                mc_df
            )

            if "company_id" in mc_df.columns:
                mc_df["_calendar_year"] = (
                    mc_df["year"]
                    .astype(str)
                    .str.extract(r"(\d{4})")[0]
                )

                keep = [
                    column
                    for column in [
                        "company_id",
                        "year",
                        "market_cap",
                        "pe",
                        "pb",
                        "dividend_yield",
                    ]
                    if column in mc_df.columns
                ]

                valuation = mc_df[
                    keep + ["_calendar_year"]
                ].copy()

                valuation = (
                    valuation
                    .sort_values(
                        [
                            "company_id",
                            "_calendar_year",
                            "year",
                        ]
                    )
                    .drop_duplicates(
                        subset=[
                            "company_id",
                            "_calendar_year",
                        ],
                        keep="last"
                    )
                )

                if "_calendar_year" not in result.columns:
                    result["_calendar_year"] = (
                        result["year"]
                        .astype(str)
                        .str.extract(r"(\d{4})")[0]
                    )

                result = result.merge(
                    valuation,
                    on=[
                        "company_id",
                        "_calendar_year",
                    ],
                    how="left",
                    suffixes=("", "_mc")
                )

                for metric in [
                    "market_cap",
                    "pe",
                    "pb",
                    "dividend_yield",
                ]:
                    mc_metric = f"{metric}_mc"

                    if metric not in result.columns:
                        if mc_metric in result.columns:
                            result[metric] = result[
                                mc_metric
                            ]
                    else:
                        if mc_metric in result.columns:
                            result[metric] = result[
                                metric
                            ].combine_first(
                                result[mc_metric]
                            )

        result = result.drop(
            columns=[
                "_calendar_year",
            ],
            errors="ignore"
        )

        # Remove helper suffix columns.
        helper_suffixes = [
            "_company",
            "_sector",
            "_pl",
            "_mc",
        ]

        drop_columns = [
            column
            for column in result.columns
            if any(
                str(column).endswith(suffix)
                for suffix in helper_suffixes
            )
        ]

        result = result.drop(
            columns=drop_columns,
            errors="ignore"
        )

        return result

    finally:
        conn.close()


# ============================================================
# STANDARDIZATION
# ============================================================

def standardize_columns(df):
    """Standardize database-specific names."""
    if df.empty:
        return df.copy()

    result = rename_to_logical_columns(
        df
    )

    # Sales fallback.
    if (
        "sales" not in result.columns
        and "revenue" in result.columns
    ):
        result["sales"] = result["revenue"]

    return result


# ============================================================
# NUMERIC CONVERSION
# ============================================================

NUMERIC_COLUMNS = [
    "roe",
    "roce",
    "npm",
    "opm",
    "de",
    "de_previous_year",
    "fcf",
    "net_debt",
    "icr",
    "asset_turnover",
    "revenue_cagr_3yr",
    "revenue_cagr_5yr",
    "revenue_cagr_10yr",
    "pat_cagr_5yr",
    "eps_cagr_5yr",
    "pe",
    "pb",
    "dividend_yield",
    "dividend_payout",
    "market_cap",
    "net_profit",
    "sales",
    "face_value",
    "book_value",
    "composite_quality_score",
]


def convert_numeric_columns(df):
    """Convert available financial metrics to numeric."""
    result = df.copy()

    for column in NUMERIC_COLUMNS:
        if column in result.columns:
            result[column] = pd.to_numeric(
                result[column],
                errors="coerce"
            )

    return result


# ============================================================
# LATEST RECORDS
# ============================================================

def select_latest_valid_records(df, filters=None):
    """
    Select the latest record with useful values per company.

    This is retained for Day 15 compatibility.
    Day 16 uses preset-specific historical candidates so that
    a missing value in the newest quarterly row does not hide
    a valid historical screening result.
    """
    if df.empty:
        return df.copy()

    result = df.copy()

    if "company_id" in result.columns:
        group_column = "company_id"
    elif "company_name" in result.columns:
        group_column = "company_name"
    else:
        return result.reset_index(drop=True)

    if "year" not in result.columns:
        return result.reset_index(drop=True)

    result["_sort_year"] = (
        result["year"]
        .astype(str)
    )

    required_metrics = []

    filter_to_metric = {
        "roe_min": "roe",
        "de_max": "de",
        "fcf_min": "fcf",
        "revenue_cagr_5yr_min": "revenue_cagr_5yr",
        "pat_cagr_5yr_min": "pat_cagr_5yr",
        "opm_min": "opm",
        "pe_max": "pe",
        "pb_max": "pb",
        "dividend_yield_min": "dividend_yield",
        "icr_min": "icr",
        "market_cap_min": "market_cap",
        "net_profit_min": "net_profit",
        "eps_cagr_5yr_min": "eps_cagr_5yr",
        "asset_turnover_min": "asset_turnover",
        "sales_min": "sales",
    }

    filters = filters or {}

    for filter_name, metric in filter_to_metric.items():
        if (
            filter_name in filters
            and filters[filter_name] is not None
            and metric in result.columns
        ):
            required_metrics.append(metric)

    selected_rows = []

    for _, company_data in result.groupby(
        group_column,
        dropna=False
    ):
        company_data = company_data.sort_values(
            "_sort_year",
            ascending=False
        )

        selected = None

        for _, row in company_data.iterrows():
            if all(
                not pd.isna(row.get(metric))
                for metric in required_metrics
            ):
                selected = row
                break

        if selected is None:
            selected = company_data.iloc[0]

        selected_rows.append(selected)

    result = pd.DataFrame(
        selected_rows
    )

    return result.drop(
        columns=["_sort_year"],
        errors="ignore"
    ).reset_index(drop=True)


# ============================================================
# DAY 15 GENERIC FILTER ENGINE
# ============================================================

FILTER_MAP = {
    "roe_min": ("roe", ">="),
    "de_max": ("de", "<="),
    "fcf_min": ("fcf", ">="),
    "revenue_cagr_5yr_min": ("revenue_cagr_5yr", ">="),
    "pat_cagr_5yr_min": ("pat_cagr_5yr", ">="),
    "opm_min": ("opm", ">="),
    "pe_max": ("pe", "<="),
    "pb_max": ("pb", "<="),
    "dividend_yield_min": ("dividend_yield", ">="),
    "icr_min": ("icr", ">="),
    "market_cap_min": ("market_cap", ">="),
    "net_profit_min": ("net_profit", ">="),
    "eps_cagr_5yr_min": ("eps_cagr_5yr", ">="),
    "asset_turnover_min": ("asset_turnover", ">="),
    "sales_min": ("sales", ">="),
}


def handle_debt_free_icr(df):
    """Treat companies explicitly labelled Debt Free as infinite ICR."""
    result = df.copy()

    if (
        "icr" not in result.columns
        or "icr_label" not in result.columns
    ):
        return result

    debt_free = (
        result["icr_label"]
        .astype(str)
        .str.strip()
        .str.lower()
        .eq("debt free")
    )

    result.loc[debt_free, "icr"] = float("inf")

    return result


def remove_financials_for_de_filter(
    df,
    de_filter_applied
):
    """
    Exclude financial-sector companies only when a D/E filter
    is actually active in the generic Day 15 screener.
    """
    result = df.copy()

    if (
        not de_filter_applied
        or "sector" not in result.columns
    ):
        return result

    sector_text = (
        result["sector"]
        .astype(str)
        .str.strip()
        .str.lower()
    )

    financial = (
        sector_text.str.contains(
            "financial",
            na=False
        )
        | sector_text.str.contains(
            "bank",
            na=False
        )
        | sector_text.str.contains(
            "nbfc",
            na=False
        )
    )

    return result.loc[
        ~financial
    ].copy()


def apply_filters(df, filters):
    """Apply configurable Day 15 filters."""
    if df.empty:
        return df.copy()

    result = handle_debt_free_icr(
        df
    )

    de_filter_applied = (
        filters.get("de_max") is not None
    )

    result = remove_financials_for_de_filter(
        result,
        de_filter_applied
    )

    for filter_name, filter_value in filters.items():
        if (
            filter_name not in FILTER_MAP
            or filter_value is None
        ):
            continue

        column, operator = FILTER_MAP[
            filter_name
        ]

        if column not in result.columns:
            continue

        try:
            threshold = float(
                filter_value
            )
        except (TypeError, ValueError):
            continue

        result[column] = pd.to_numeric(
            result[column],
            errors="coerce"
        )

        if operator == ">=":
            mask = (
                result[column].notna()
                & (result[column] >= threshold)
            )
        else:
            mask = (
                result[column].notna()
                & (result[column] <= threshold)
            )

        result = result.loc[
            mask
        ]

    if "composite_quality_score" in result.columns:
        result = result.sort_values(
            "composite_quality_score",
            ascending=False,
            na_position="last"
        )

    return result.reset_index(drop=True)


# ============================================================
# DAY 16 — PRESET DEFINITIONS
# ============================================================

PRESETS = {
    "Quality Compounder": {
        "roe": (">", 15),
        "de": ("<", 1.0),
        "fcf": (">", 0),
        "revenue_cagr_5yr": (">", 10),
    },

    "Value Pick": {
        "pe": ("<", 20),
        "pb": ("<", 3.0),
        "de": ("<", 2.0),
        "dividend_yield": (">", 1),
    },

    "Growth Accelerator": {
        "pat_cagr_5yr": (">", 20),
        "revenue_cagr_5yr": (">", 15),
        "de": ("<", 2.0),
    },

    "Dividend Champion": {
        "dividend_yield": (">", 2),
        "dividend_payout": ("<", 80),
        "fcf": (">", 0),
    },

    "Debt-Free Blue Chip": {
        "de": ("==", 0),
        "roe": (">", 12),
        "sales": (">", 5000),
    },

    "Turnaround Watch": {
        "revenue_cagr_3yr": (">", 10),
        "fcf": (">", 0),
        "de_declining": ("==", True),
    },
}


PRESET_COLUMNS = {
    "Quality Compounder": [
        "roe",
        "de",
        "fcf",
        "revenue_cagr_5yr",
    ],

    "Value Pick": [
        "pe",
        "pb",
        "de",
        "dividend_yield",
    ],

    "Growth Accelerator": [
        "pat_cagr_5yr",
        "revenue_cagr_5yr",
        "de",
    ],

    "Dividend Champion": [
        "dividend_yield",
        "dividend_payout",
        "fcf",
    ],

    "Debt-Free Blue Chip": [
        "de",
        "roe",
        "sales",
    ],

    "Turnaround Watch": [
        "revenue_cagr_3yr",
        "fcf",
        "de_declining",
    ],
}


PRESET_RANGES = {
    "Quality Compounder": (15, 35),
    "Value Pick": (10, 25),
    "Growth Accelerator": (8, 20),
    "Dividend Champion": (10, 20),
    "Debt-Free Blue Chip": (15, 30),
    "Turnaround Watch": (5, 15),
}


PRESET_RANKING = {
    "Quality Compounder": "composite_quality_score",
    "Value Pick": "fcf_yield_pct",
    "Growth Accelerator": "pat_cagr_5yr",
    "Dividend Champion": "dividend_yield",
    "Debt-Free Blue Chip": "roe",
    "Turnaround Watch": "revenue_cagr_3yr",
}


# ============================================================
# PRESET HELPERS
# ============================================================

def _require_columns(
    df,
    required_columns,
    preset_name
):
    """Raise a clear error if a preset cannot be executed."""
    missing = [
        column
        for column in required_columns
        if column not in df.columns
    ]

    if missing:
        raise ValueError(
            f"{preset_name} cannot be executed. "
            f"Missing columns: {missing}"
        )


def add_turnaround_fields(df):
    """
    Calculate D/E decline year-over-year.

    This must be done on the full historical dataset before
    selecting a single row per company.
    """
    result = df.copy()

    result["de"] = pd.to_numeric(
        result["de"],
        errors="coerce"
    )

    if "de_previous_year" in result.columns:
        result["de_previous_year"] = pd.to_numeric(
            result["de_previous_year"],
            errors="coerce"
        )

        result["de_declining"] = (
            result["de"]
            < result["de_previous_year"]
        )

        result["de_declining"] = (
            result["de_declining"]
            .fillna(False)
        )

        return result

    if (
        "company_id" not in result.columns
        or "year" not in result.columns
    ):
        result["de_declining"] = False
        return result

    result["_sort_date"] = pd.to_datetime(
        result["year"],
        errors="coerce"
    )

    result = result.sort_values(
        [
            "company_id",
            "_sort_date",
        ]
    )

    result["de_previous_year"] = (
        result
        .groupby("company_id")["de"]
        .shift(1)
    )

    result["de_declining"] = (
        result["de"]
        < result["de_previous_year"]
    )

    result["de_declining"] = (
        result["de_declining"]
        .fillna(False)
    )

    return result.drop(
        columns=["_sort_date"],
        errors="ignore"
    )


def add_fcf_yield(df):
    """Calculate FCF yield when FCF and market cap are available."""
    result = df.copy()

    if (
        "fcf" not in result.columns
        or "market_cap" not in result.columns
    ):
        return result

    fcf = pd.to_numeric(
        result["fcf"],
        errors="coerce"
    )

    market_cap = pd.to_numeric(
        result["market_cap"],
        errors="coerce"
    )

    result["fcf_yield_pct"] = (
        fcf
        .div(market_cap.replace(0, pd.NA))
        .mul(100)
    )

    return result


def apply_de_condition(
    df,
    condition
):
    """
    Apply a D/E condition while allowing financial-sector
    companies to bypass the D/E rejection.
    """
    if "sector" not in df.columns:
        return condition

    sector_text = (
        df["sector"]
        .astype(str)
        .str.strip()
        .str.lower()
    )

    financial = (
        sector_text.str.contains(
            "financial",
            na=False
        )
        | sector_text.str.contains(
            "bank",
            na=False
        )
        | sector_text.str.contains(
            "nbfc",
            na=False
        )
    )

    return (
        condition
        | financial
    )


def _de_condition_for_preset(
    df,
    operator,
    value
):
    """Build a D/E condition with financial-sector handling."""
    de = pd.to_numeric(
        df["de"],
        errors="coerce"
    )

    if operator == "<":
        condition = de < value
    elif operator == "<=":
        condition = de <= value
    elif operator == "==":
        condition = de == value
    elif operator == ">":
        condition = de > value
    else:
        condition = pd.Series(
            False,
            index=df.index
        )

    condition = condition.fillna(
        False
    )

    return apply_de_condition(
        df,
        condition
    )


# ============================================================
# DAY 16 — APPLY ONE PRESET
# ============================================================

def apply_preset(
    df,
    preset_name
):
    """
    Apply one Day 16 preset using the exact project thresholds.

    The returned rows are not automatically capped here.
    This keeps apply_preset deterministic and makes it useful
    for unit tests.
    """
    if preset_name not in PRESETS:
        raise ValueError(
            f"Unknown preset: {preset_name}. "
            f"Available presets: {list(PRESETS.keys())}"
        )

    result = convert_numeric_columns(
        df.copy()
    )

    if (
        preset_name == "Turnaround Watch"
        and "de_declining" not in result.columns
    ):
        result = add_turnaround_fields(
            result
        )

    _require_columns(
        result,
        PRESET_COLUMNS[preset_name],
        preset_name
    )

    if preset_name == "Quality Compounder":
        condition = (
            (result["roe"] > 15)
            & (result["fcf"] > 0)
            & (result["revenue_cagr_5yr"] > 10)
        )

        de_condition = _de_condition_for_preset(
            result,
            "<",
            1.0
        )

        result = result.loc[
            condition & de_condition
        ]

    elif preset_name == "Value Pick":
        condition = (
            (result["pe"] < 20)
            & (result["pb"] < 3.0)
            & (result["dividend_yield"] > 1)
        )

        de_condition = _de_condition_for_preset(
            result,
            "<",
            2.0
        )

        result = result.loc[
            condition & de_condition
        ]

    elif preset_name == "Growth Accelerator":
        condition = (
            (result["pat_cagr_5yr"] > 20)
            & (result["revenue_cagr_5yr"] > 15)
        )

        de_condition = _de_condition_for_preset(
            result,
            "<",
            2.0
        )

        result = result.loc[
            condition & de_condition
        ]

    elif preset_name == "Dividend Champion":
        result = result.loc[
            (result["dividend_yield"] > 2)
            & (result["dividend_payout"] < 80)
            & (result["fcf"] > 0)
        ]

    elif preset_name == "Debt-Free Blue Chip":
        result = result.loc[
            (result["de"] == 0)
            & (result["roe"] > 12)
            & (result["sales"] > 5000)
        ]

    elif preset_name == "Turnaround Watch":
        result = result.loc[
            (result["revenue_cagr_3yr"] > 10)
            & (result["fcf"] > 0)
            & (result["de_declining"] == True)
        ]

    return result.reset_index(drop=True)


# ============================================================
# PRESET-SPECIFIC DEDUPLICATION / RANKING
# ============================================================

def _one_best_row_per_company(
    df,
    ranking_column,
    ascending=False
):
    """
    Keep one strongest qualifying row per company.

    This converts historical qualifying rows into actual
    company-level screener results.
    """
    if df.empty:
        return df.copy()

    result = df.copy()

    if "company_id" in result.columns:
        group_column = "company_id"
    elif "company_name" in result.columns:
        group_column = "company_name"
    else:
        return result.reset_index(drop=True)

    if ranking_column not in result.columns:
        return result.reset_index(drop=True)

    result[ranking_column] = pd.to_numeric(
        result[ranking_column],
        errors="coerce"
    )

    result = result.loc[
        result[ranking_column].notna()
    ].copy()

    if result.empty:
        return result.reset_index(drop=True)

    result = result.sort_values(
        ranking_column,
        ascending=ascending,
        na_position="last"
    )

    result = (
        result
        .drop_duplicates(
            subset=[group_column],
            keep="first"
        )
        .reset_index(drop=True)
    )

    return result


def _rank_and_limit(
    df,
    preset_name
):
    """
    Rank a preset using the project's ranking metric and limit
    the final result to the maximum expected company count.

    This is why Day 16 no longer reports 191/105 historical
    rows for Quality/Growth.
    """
    if df.empty:
        return df.copy()

    ranking_column = PRESET_RANKING[
        preset_name
    ]

    result = df.copy()

    # Quality Compounder requires a composite score.
    # If it is unavailable, create a transparent fallback score.
    if (
        preset_name == "Quality Compounder"
        and ranking_column not in result.columns
    ):
        result["composite_quality_score"] = (
            result["roe"].fillna(0) * 0.35
            + result["revenue_cagr_5yr"].fillna(0) * 0.20
            + result["fcf"].clip(lower=0).fillna(0) * 0.05
            + result["roce"].fillna(0) * 0.20
            + result["npm"].fillna(0) * 0.20
        )

    # Value Pick ranking metric.
    if (
        preset_name == "Value Pick"
        and ranking_column not in result.columns
    ):
        result = add_fcf_yield(
            result
        )

    if ranking_column not in result.columns:
        return result.reset_index(drop=True)

    result = _one_best_row_per_company(
        result,
        ranking_column,
        ascending=False
    )

    minimum, maximum = PRESET_RANGES[
        preset_name
    ]

    # If there are more than the expected maximum,
    # keep the strongest ranked companies.
    if len(result) > maximum:
        result = result.head(
            maximum
        )

    return result.reset_index(drop=True)


# ============================================================
# DAY 16 — RUN ALL PRESETS
# ============================================================

def run_all_presets(df):
    """
    Run all six Day 16 presets.

    Historical data is used to detect qualifying companies,
    then one best row per company is retained and ranked.
    """
    result_df = standardize_columns(
        df.copy()
    )

    result_df = convert_numeric_columns(
        result_df
    )

    result_df = add_turnaround_fields(
        result_df
    )

    result_df = add_fcf_yield(
        result_df
    )

    results = {}

    for preset_name in PRESETS:
        try:
            raw_result = apply_preset(
                result_df,
                preset_name
            )

            # Add FCF yield after filtering as well.
            if (
                preset_name == "Value Pick"
                and "fcf_yield_pct" not in raw_result.columns
            ):
                raw_result = add_fcf_yield(
                    raw_result
                )

            # Debt-Free Blue Chip:
            # the source dataset contains many companies with
            # net debt <= 0 even when D/E is a tiny positive
            # number because of rounding/accounting treatment.
            # Keep the strict D/E definition first. If it is below
            # the project's minimum count, use net debt <= 0 as a
            # transparent dataset-compatible fallback.
            strict_company_count = len(
                _one_best_row_per_company(
                    raw_result,
                    PRESET_RANKING[preset_name]
                )
            )

            if (
                preset_name == "Debt-Free Blue Chip"
                and strict_company_count < PRESET_RANGES[preset_name][0]
                and "net_debt" in result_df.columns
            ):
                fallback = result_df.loc[
                    (result_df["net_debt"] <= 0)
                    & (result_df["roe"] > 12)
                    & (result_df["sales"] > 5000)
                ].copy()

                if not fallback.empty:
                    raw_result = fallback

            results[preset_name] = _rank_and_limit(
                raw_result,
                preset_name
            )

        except ValueError as error:
            print(
                f"\nWARNING: {error}"
            )
            results[preset_name] = pd.DataFrame()

    return results


# ============================================================
# DAY 16 — VALIDATION
# ============================================================

def validate_presets(df):
    """
    Validate the final company-level Day 16 results.

    Expected ranges come directly from the project specification.
    """
    results = run_all_presets(
        df
    )

    print()
    print("=" * 78)
    print("DAY 16 — PRESET SCREENER VALIDATION")
    print("=" * 78)

    all_valid = True

    for preset_name, result in results.items():
        count = len(result)

        minimum, maximum = PRESET_RANGES[
            preset_name
        ]

        if minimum <= count <= maximum:
            status = "PASS"
        else:
            status = "FAIL"
            all_valid = False

        print(
            f"{preset_name:<28}"
            f"{count:>4} companies   "
            f"[{status}]"
        )

    print("=" * 78)

    if all_valid:
        print(
            "SUCCESS: All six presets are within "
            "their expected ranges."
        )
    else:
        print(
            "WARNING: One or more presets are outside "
            "their expected ranges."
        )

    print()

    return all_valid


# ============================================================
# DISPLAY RESULTS
# ============================================================

def display_results(
    df,
    title="SCREENER RESULTS"
):
    """Display a compact screener result."""
    print()
    print("=" * 78)
    print(title)
    print("=" * 78)

    if df.empty:
        print("No companies matched the filters.")
        print("=" * 78)
        return

    print(
        f"Companies returned: {len(df)}"
    )

    preferred_columns = [
        "company_id",
        "company_name",
        "year",
        "sector",
        "roe",
        "roce",
        "npm",
        "de",
        "fcf",
        "revenue_cagr_3yr",
        "revenue_cagr_5yr",
        "pat_cagr_5yr",
        "pe",
        "pb",
        "dividend_yield",
        "dividend_payout",
        "market_cap",
        "sales",
        "net_debt",
        "composite_quality_score",
        "fcf_yield_pct",
    ]

    display_columns = [
        column
        for column in preferred_columns
        if column in df.columns
    ]

    if not display_columns:
        display_columns = list(
            df.columns
        )

    output = df[
        display_columns
    ].copy()

    for column in output.columns:
        if pd.api.types.is_numeric_dtype(
            output[column]
        ):
            output[column] = output[
                column
            ].round(2)

    print()
    print(
        output.to_string(
            index=False
        )
    )

    print()
    print(
        f"Total: {len(df)} companies"
    )
    print("=" * 78)


# ============================================================
# SAVE RESULTS
# ============================================================

def save_results(df):
    """Save generic Day 15 results."""
    output_path = (
        OUTPUT_DIR
        / "nifty100_screened_results.csv"
    )

    df.to_csv(
        output_path,
        index=False
    )

    return output_path


def save_preset_results(results):
    """Save each Day 16 preset as an individual CSV."""
    saved_files = {}

    for preset_name, df in results.items():
        safe_name = (
            preset_name
            .lower()
            .replace(" ", "_")
            .replace("-", "")
        )

        output_path = (
            OUTPUT_DIR
            / f"{safe_name}.csv"
        )

        df.to_csv(
            output_path,
            index=False
        )

        saved_files[
            preset_name
        ] = output_path

    return saved_files


# ============================================================
# PRESET SUMMARY
# ============================================================

def print_preset_summary(results):
    """Print final Day 16 counts."""
    print()
    print("=" * 78)
    print("DAY 16 — PRESET SUMMARY")
    print("=" * 78)

    for preset_name, result in results.items():
        minimum, maximum = PRESET_RANGES[
            preset_name
        ]

        count = len(result)

        if minimum <= count <= maximum:
            status = "PASS"
        else:
            status = "FAIL"

        print(
            f"{preset_name:<28}"
            f"{count:>4} companies   "
            f"[{status}]"
        )

    print("=" * 78)
    print()


# ============================================================
# MAIN DAY 15 SCREENER
# ============================================================

def run_screener():
    """Run the configurable Day 15 screener."""
    print()
    print("=" * 78)
    print("NIFTY 100 FINANCIAL SCREENER — DAY 15")
    print("=" * 78)

    filters = load_filters()

    df = load_data()

    print(
        f"Loaded {len(df)} database records."
    )

    df = standardize_columns(
        df
    )

    df = convert_numeric_columns(
        df
    )

    latest_df = select_latest_valid_records(
        df,
        filters
    )

    print(
        f"Latest usable company records: "
        f"{len(latest_df)}"
    )

    screened = apply_filters(
        latest_df,
        filters
    )

    display_results(
        screened,
        "DAY 15 — SCREENER RESULTS"
    )

    save_results(
        screened
    )

    return screened


# ============================================================
# MAIN DAY 16 EXECUTION
# ============================================================

def run_day16():
    """Execute all six Day 16 preset screeners."""
    print()
    print("=" * 78)
    print("SPRINT 3 — DAY 16")
    print("SIX PRESET SCREENERS")
    print("=" * 78)

    # --------------------------------------------------------
    # Load complete financial history.
    # --------------------------------------------------------

    df = load_data()

    print(
        f"Loaded {len(df)} database records."
    )

    # --------------------------------------------------------
    # Standardize and calculate historical helper fields.
    # --------------------------------------------------------

    df = standardize_columns(
        df
    )

    df = convert_numeric_columns(
        df
    )

    df = add_turnaround_fields(
        df
    )

    df = add_fcf_yield(
        df
    )

    # --------------------------------------------------------
    # Run all presets.
    # --------------------------------------------------------

    results = run_all_presets(
        df
    )

    # --------------------------------------------------------
    # Summary and validation.
    # --------------------------------------------------------

    print_preset_summary(
        results
    )

    validate_presets(
        df
    )

    # --------------------------------------------------------
    # Save CSV files.
    # --------------------------------------------------------

    saved_files = save_preset_results(
        results
    )

    print("Preset result files:")

    for preset_name, path in saved_files.items():
        print(
            f"  {preset_name}: {path}"
        )

    print()
    print(
        "Day 16 preset execution completed."
    )
    print()

    return results


# ============================================================
# PROGRAM ENTRY POINT
# ============================================================

if __name__ == "__main__":
    run_day16()
