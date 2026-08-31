import os
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


# ============================================================
# DATABASE HELPERS
# ============================================================

def get_connection():
    """Create SQLite database connection."""
    return sqlite3.connect(DB_PATH)


def get_tables(conn):
    """Return available database tables."""
    query = """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
        ORDER BY name
    """

    return pd.read_sql_query(query, conn)["name"].tolist()


def get_columns(conn, table_name):
    """Return columns available in a table."""
    rows = conn.execute(
        f'PRAGMA table_info("{table_name}")'
    ).fetchall()

    return [row[1] for row in rows]


def find_table(conn, possible_names):
    """Find the first matching table."""
    tables = get_tables(conn)

    for name in possible_names:
        if name in tables:
            return name

    return None


# ============================================================
# CONFIGURATION
# ============================================================

def load_config():
    """Load screener configuration from YAML."""

    if not CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"Configuration file not found:\n{CONFIG_PATH}"
        )

    with open(CONFIG_PATH, "r", encoding="utf-8") as file:
        config = yaml.safe_load(file) or {}

    return config.get("filters", {})


# ============================================================
# COLUMN MAPPING
# ============================================================

COLUMN_ALIASES = {

    # ROE
    # Company ID
    "company_id": [
        "company_id",
        "id",
        "companyid",
    ],

    "roe": [
        "roe",
        "roe_percentage",
        "return_on_equity_pct",
        "return_on_equity",
        "return_on_equity_percentage",
    ],

    # Debt / Equity
    "de": [
        "de",
        "de_ratio",
        "debt_to_equity",
        "debt_to_equity_pct",
        "debt_to_equity_ratio",
    ],

    # Free cash flow
    "fcf": [
        "fcf",
        "free_cash_flow",
        "free_cash_flow_cr",
    ],

    # Revenue CAGR
    "revenue_cagr_5yr": [
        "revenue_cagr_5yr",
        "revenue_cagr_5yr_pct",
        "compounded_sales_growth",
        "sales_cagr_5yr",
    ],

    # PAT CAGR
    "pat_cagr_5yr": [
        "pat_cagr_5yr",
        "pat_cagr_5yr_pct",
        "profit_cagr_5yr",
        "profit_growth_5yr",
    ],

    # Operating profit margin
    "opm": [
        "opm",
        "operating_profit_margin",
        "operating_profit_margin_pct",
        "opm_pct",
    ],

    # PE
    "pe": [
        "pe",
        "pe_ratio",
        "price_to_earnings",
    ],

    # PB
    "pb": [
        "pb",
        "pb_ratio",
        "price_to_book",
    ],

    # Dividend yield
    "dividend_yield": [
        "dividend_yield",
        "dividend_yield_pct",
    ],

    # Interest coverage
    "icr": [
        "icr",
        "interest_coverage",
        "interest_coverage_ratio",
    ],

    # Market cap
    "market_cap": [
        "market_cap",
        "market_cap_cr",
        "market_capitalization",
    ],

    # Net profit
    "net_profit": [
        "net_profit",
        "net_profit_cr",
        "net_profit_margin",
        "net_profit_margin_pct",
    ],

    # EPS CAGR
    "eps_cagr_5yr": [
        "eps_cagr_5yr",
        "eps_cagr_5yr_pct",
        "eps_growth_5yr",
    ],

    # Asset turnover
    "asset_turnover": [
        "asset_turnover",
        "asset_turnover_ratio",
    ],

    # Sales
    "sales": [
        "sales",
        "sales_cr",
        "revenue",
        "revenue_cr",
        "total_sales",
    ],

    # Face value
    "face_value": [
        "face_value",
    ],

    # Book value
    "book_value": [
        "book_value",
    ],

    # ROCE
    "roce": [
        "roce",
        "roce_percentage",
        "return_on_capital_employed",
    ],

    # Net debt
    "net_debt": [
        "net_debt",
        "net_debt_cr",
    ],
}


def find_column(available_columns, logical_name):
    """
    Find a real database column for a logical metric.
    """

    available_lower = {
        column.lower(): column
        for column in available_columns
    }

    aliases = COLUMN_ALIASES.get(logical_name, [logical_name])

    for alias in aliases:
        if alias.lower() in available_lower:
            return available_lower[alias.lower()]

    return None


# ============================================================
# DATA LOADING
# ============================================================

def load_data():
    """
    Load financial data from SQLite.

    This function dynamically detects available columns so the
    screener does not crash when an optional column is missing.
    """

    conn = get_connection()

    try:

        tables = get_tables(conn)

        print("\nAvailable database tables:")
        for table in tables:
            print(f"  - {table}")

        financial_table = find_table(
            conn,
            [
                "financial_ratios",
                "financial_ratio",
                "ratios",
            ],
        )

        company_table = find_table(
            conn,
            [
                "companies",
                "company",
            ],
        )

        if financial_table is None:
            raise RuntimeError(
                "Could not find financial_ratios table."
            )

        financial_columns = get_columns(
            conn,
            financial_table
        )

        print(
            f"\nFinancial table: {financial_table}"
        )

        print("Available financial columns:")
        print(", ".join(financial_columns))

        # ----------------------------------------------------
        # Read financial data
        # ----------------------------------------------------

        financial_df = pd.read_sql_query(
            f'SELECT * FROM "{financial_table}"',
            conn,
        )

        if financial_df.empty:
            return pd.DataFrame()

        # ----------------------------------------------------
        # Read company information
        # ----------------------------------------------------

        if company_table:

            company_columns = get_columns(
                conn,
                company_table
            )

            print(
                f"\nCompany table: {company_table}"
            )

            print("Available company columns:")
            print(", ".join(company_columns))

            company_df = pd.read_sql_query(
                f'SELECT * FROM "{company_table}"',
                conn,
            )

            # Find company ID columns
            financial_company_id = find_column(
                financial_columns,
                "company_id",
            )

            company_id = find_column(
                company_columns,
                "company_id",
            )

            if (
                financial_company_id
                and company_id
                and financial_company_id in financial_df.columns
                and company_id in company_df.columns
            ):

                financial_df = financial_df.merge(
                    company_df,
                    left_on=financial_company_id,
                    right_on=company_id,
                    how="left",
                    suffixes=("", "_company"),
                )

        return financial_df

    finally:
        conn.close()


# ============================================================
# STANDARDIZE COLUMNS
# ============================================================

def standardize_columns(df):
    """
    Convert database-specific column names into the standard
    names used by the screener.
    """

    if df.empty:
        return df

    available = list(df.columns)

    result = df.copy()

    for logical_name in COLUMN_ALIASES:

        actual_column = find_column(
            available,
            logical_name
        )

        if actual_column:

            # Don't overwrite if standard name already exists
            if logical_name not in result.columns:

                result[logical_name] = result[
                    actual_column
                ]

    # --------------------------------------------------------
    # Sales fallback
    # --------------------------------------------------------
    # In many datasets, "sales" is stored as "revenue".
    # If revenue exists, expose it as the standard "sales" metric.
    if "sales" not in result.columns and "revenue" in result.columns:
        result["sales"] = result["revenue"]

    # --------------------------------------------------------
    # Company name
    # --------------------------------------------------------

    if "company_name" not in result.columns:

        possible_names = [
            "name",
            "company",
            "companyname",
            "company_name",
            "stock_name",
        ]

        for column in available:

            if column.lower() in possible_names:

                result["company_name"] = result[column]
                break

    # --------------------------------------------------------
    # Company ID
    # --------------------------------------------------------

    if "company_id" not in result.columns:

        for column in available:

            if column.lower() == "id":

                result["company_id"] = result[column]
                break

    return result


# ============================================================
# NUMERIC CONVERSION
# ============================================================

def convert_numeric_columns(df):
    """Convert metric columns to numeric values."""

    metric_columns = [
        "roe",
        "de",
        "fcf",
        "revenue_cagr_5yr",
        "pat_cagr_5yr",
        "opm",
        "pe",
        "pb",
        "dividend_yield",
        "icr",
        "market_cap",
        "net_profit",
        "eps_cagr_5yr",
        "asset_turnover",
        "sales",
        "face_value",
        "book_value",
        "roce",
        "net_debt",
    ]

    for column in metric_columns:

        if column in df.columns:

            df[column] = pd.to_numeric(
                df[column],
                errors="coerce"
            )

    return df


# ============================================================
# LATEST VALID DATA
# ============================================================

def select_latest_valid_records(df, filters):
    """
    Select the latest useful record for each company.

    IMPORTANT:
    We do NOT simply select the newest row.

    If the newest row contains NaN for ROE, PE, etc., we look
    backwards for the latest row containing the required data.

    This fixes the issue where 2024-09 records with NaN values
    were eliminating otherwise valid companies.
    """

    if df.empty:
        return df

    result = df.copy()

    # --------------------------------------------------------
    # Determine company column
    # --------------------------------------------------------

    if "company_id" in result.columns:
        group_column = "company_id"

    elif "company_name" in result.columns:
        group_column = "company_name"

    else:
        print(
            "WARNING: Company identifier not found."
        )

        return result

    # --------------------------------------------------------
    # Determine year/date column
    # --------------------------------------------------------

    year_column = None

    for column in [
        "year",
        "date",
        "period",
        "financial_year",
        "fy",
    ]:

        if column in result.columns:
            year_column = column
            break

    if year_column is None:

        print(
            "WARNING: Year column not found."
        )

        return result

    # --------------------------------------------------------
    # Convert year to sortable value
    # --------------------------------------------------------

    result["_sort_year"] = result[
        year_column
    ].astype(str)

    result = result.sort_values(
        [group_column, "_sort_year"]
    )

    # --------------------------------------------------------
    # Metrics actually required by filters
    # --------------------------------------------------------

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

    for filter_name, metric in filter_to_metric.items():

        if filter_name in filters:
            value = filters[filter_name]

            if value is not None and metric in result.columns:
                required_metrics.append(metric)

    # --------------------------------------------------------
    # Select latest row with usable values
    # --------------------------------------------------------

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

        if required_metrics:

            for _, row in company_data.iterrows():

                valid = True

                for metric in required_metrics:

                    if pd.isna(row.get(metric)):
                        valid = False
                        break

                if valid:
                    selected = row
                    break

        # If no row contains all required values,
        # use the latest row instead.
        if selected is None:
            selected = company_data.iloc[0]

        selected_rows.append(selected)

    result = pd.DataFrame(selected_rows)

    result = result.drop(
        columns=["_sort_year"],
        errors="ignore"
    )

    return result.reset_index(drop=True)


# ============================================================
# FILTER ENGINE
# ============================================================

def apply_filters(df, filters):
    """
    Apply configured screening filters.

    Missing database columns are skipped rather than causing
    the entire screener to fail.
    """

    if df.empty:
        return df

    result = df.copy()

    print("\nApplying filters...")
    print("-" * 70)

    filter_map = {

        "roe_min": (
            "roe",
            ">="
        ),

        "de_max": (
            "de",
            "<="
        ),

        "fcf_min": (
            "fcf",
            ">="
        ),

        "revenue_cagr_5yr_min": (
            "revenue_cagr_5yr",
            ">="
        ),

        "pat_cagr_5yr_min": (
            "pat_cagr_5yr",
            ">="
        ),

        "opm_min": (
            "opm",
            ">="
        ),

        "pe_max": (
            "pe",
            "<="
        ),

        "pb_max": (
            "pb",
            "<="
        ),

        "dividend_yield_min": (
            "dividend_yield",
            ">="
        ),

        "icr_min": (
            "icr",
            ">="
        ),

        "market_cap_min": (
            "market_cap",
            ">="
        ),

        "net_profit_min": (
            "net_profit",
            ">="
        ),

        "eps_cagr_5yr_min": (
            "eps_cagr_5yr",
            ">="
        ),

        "asset_turnover_min": (
            "asset_turnover",
            ">="
        ),

        "sales_min": (
            "sales",
            ">="
        ),
    }

    for filter_name, (
        column,
        operator
    ) in filter_map.items():

        if filter_name not in filters:
            continue

        threshold = filters[filter_name]

        if threshold is None:
            continue

        # ----------------------------------------------------
        # Column doesn't exist
        # ----------------------------------------------------

        if column not in result.columns:

            print(
                f"Skipping {filter_name}: "
                f"'{column}' is not available."
            )

            continue

        # ----------------------------------------------------
        # Convert threshold
        # ----------------------------------------------------

        try:
            threshold = float(threshold)

        except (TypeError, ValueError):

            print(
                f"Skipping {filter_name}: "
                f"invalid value '{threshold}'."
            )

            continue

        # ----------------------------------------------------
        # Numeric conversion
        # ----------------------------------------------------

        result[column] = pd.to_numeric(
            result[column],
            errors="coerce"
        )

        before = len(result)

        # ----------------------------------------------------
        # Apply filter
        # ----------------------------------------------------

        if operator == ">=":

            result = result[
                result[column].notna()
                & (result[column] >= threshold)
            ]

        elif operator == "<=":

            result = result[
                result[column].notna()
                & (result[column] <= threshold)
            ]

        after = len(result)

        print(
            f"{filter_name}: "
            f"{threshold:g} -> "
            f"{after} rows"
        )

        # ----------------------------------------------------
        # Stop early
        # ----------------------------------------------------

        if result.empty:

            print(
                f"\nNo rows remain after "
                f"{filter_name}."
            )

            break

    print("-" * 70)

    return result.reset_index(drop=True)


# ============================================================
# DISPLAY
# ============================================================

def display_results(df):
    """Display screener results."""

    print("\n")
    print("=" * 80)
    print("NIFTY 100 STOCK SCREENER RESULTS")
    print("=" * 80)

    if df.empty:

        print(
            "\nNo companies matched the selected filters."
        )

        print("=" * 80)

        return

    # --------------------------------------------------------
    # Preferred output columns
    # --------------------------------------------------------

    preferred_columns = [
        "company_name",
        "year",
        "roe",
        "de",
        "fcf",
        "revenue_cagr_5yr",
        "pat_cagr_5yr",
        "opm",
        "pe",
        "pb",
        "dividend_yield",
        "icr",
        "market_cap",
        "net_profit",
        "eps_cagr_5yr",
        "asset_turnover",
        "sales",
    ]

    display_columns = [
        column
        for column in preferred_columns
        if column in df.columns
    ]

    # If none of the preferred columns exist,
    # show everything.
    if not display_columns:

        display_columns = list(df.columns)

    output = df[display_columns].copy()

    # --------------------------------------------------------
    # Round numeric values
    # --------------------------------------------------------

    for column in output.columns:

        if pd.api.types.is_numeric_dtype(
            output[column]
        ):

            output[column] = output[column].round(2)

    # --------------------------------------------------------
    # Print
    # --------------------------------------------------------

    pd.set_option(
        "display.max_columns",
        None
    )

    pd.set_option(
        "display.width",
        200
    )

    pd.set_option(
        "display.max_rows",
        200
    )

    print()

    print(output.to_string(index=False))

    print("\n")
    print("-" * 80)

    print(
        f"Total screened rows: {len(df)}"
    )

    if "company_name" in df.columns:

        print(
            f"Unique companies: "
            f"{df['company_name'].nunique()}"
        )

    elif "company_id" in df.columns:

        print(
            f"Unique companies: "
            f"{df['company_id'].nunique()}"
        )

    print("-" * 80)


# ============================================================
# SAVE RESULTS
# ============================================================

def save_results(df):
    """Save screened results to output folder."""

    if df.empty:
        print("\nNo results to save.")
        return

    output_dir = BASE_DIR / "output"
    output_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    output_file = (
        output_dir /
        "nifty100_screened_results.csv"
    )

    df.to_csv(
        output_file,
        index=False
    )

    print(
        f"\nResults saved to:\n{output_file}"
    )


# ============================================================
# MAIN SCREENER
# ============================================================

def run_screener():

    print("=" * 80)
    print("NIFTY 100 STOCK SCREENER")
    print("=" * 80)

    print(
        f"\nDatabase: {DB_PATH}"
    )

    print(
        f"Config:   {CONFIG_PATH}"
    )

    # --------------------------------------------------------
    # Load configuration
    # --------------------------------------------------------

    try:

        filters = load_config()

    except Exception as error:

        print(
            f"\nERROR loading configuration:"
            f"\n{error}"
        )

        return pd.DataFrame()

    print(
        "\nConfiguration loaded successfully."
    )

    print("\nActive filters:")
    if filters:
        for name, value in filters.items():
            print(f"  - {name}: {value}")
    else:
        print("  None")

    # --------------------------------------------------------
    # Load data
    # --------------------------------------------------------

    print("\nLoading data...")

    try:

        df = load_data()

    except Exception as error:

        print(
            f"\nERROR loading database:"
            f"\n{error}"
        )

        return pd.DataFrame()

    if df.empty:

        print(
            "\nNo data found in database."
        )

        return df

    print(
        f"\nTotal rows loaded: {len(df)}"
    )

    # --------------------------------------------------------
    # Standardize columns
    # --------------------------------------------------------

    df = standardize_columns(df)

    df = convert_numeric_columns(df)

    print("\nStandardized columns:")

    print(
        ", ".join(df.columns)
    )

    # --------------------------------------------------------
    # Select latest VALID record
    # --------------------------------------------------------

    print(
        "\nSelecting latest available "
        "record for each company..."
    )

    df = select_latest_valid_records(
        df,
        filters
    )

    print(
        f"Latest usable company records: "
        f"{len(df)}"
    )

    # --------------------------------------------------------
    # Apply filters
    # --------------------------------------------------------

    screened = apply_filters(
        df,
        filters
    )

    # --------------------------------------------------------
    # Display
    # --------------------------------------------------------

    display_results(screened)

    # --------------------------------------------------------
    # Save
    # --------------------------------------------------------

    save_results(screened)

    return screened


# ============================================================
# PROGRAM ENTRY POINT
# ============================================================

if __name__ == "__main__":

    run_screener()