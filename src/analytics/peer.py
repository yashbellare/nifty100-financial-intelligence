"""
Peer Analysis Engine
--------------------
Builds peer-group percentile rankings from financial_ratios.

Database tables used:
    - financial_ratios
    - peer_groups
    - peer_percentiles

Important:
    company_metrics does NOT exist in the current database.
"""

import sqlite3
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------
# DATABASE PATH
# ---------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "nifty100.db"


# ---------------------------------------------------------------------
# METRIC MAPPING
# ---------------------------------------------------------------------

METRIC_COLUMNS = {
    "de": "debt_to_equity",
    "roe": "return_on_equity_pct",
    "roce": "return_on_capital_employed_pct",
    "npm": "net_profit_margin_pct",
    "fcf": "free_cash_flow_cr",
    "interest_coverage": "interest_coverage",
    "asset_turnover": "asset_turnover",
    "pat_cagr_3yr": "pat_cagr_3yr",
    "pat_cagr_5yr": "pat_cagr_5yr",
    "revenue_cagr_3yr": "revenue_cagr_3yr",
    "revenue_cagr_5yr": "revenue_cagr_5yr",
    "eps_cagr_3yr": "eps_cagr_3yr",
    "eps_cagr_5yr": "eps_cagr_5yr",
}


# Metrics where lower values are considered better.
LOWER_IS_BETTER = {
    "de",
}


# ---------------------------------------------------------------------
# DATABASE HELPERS
# ---------------------------------------------------------------------

def get_connection(db_path: Optional[Path] = None):
    """Create and return a SQLite connection."""
    path = db_path or DB_PATH

    if not path.exists():
        raise FileNotFoundError(f"Database not found: {path}")

    return sqlite3.connect(path)


def table_exists(conn, table_name: str) -> bool:
    """Check whether a table exists."""
    row = conn.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table'
          AND name = ?
        """,
        (table_name,),
    ).fetchone()

    return row is not None


def get_columns(conn, table_name: str):
    """Return column names for a table."""
    rows = conn.execute(
        f"PRAGMA table_info({table_name})"
    ).fetchall()

    return [row[1] for row in rows]


# ---------------------------------------------------------------------
# PEER GROUPS
# ---------------------------------------------------------------------

def get_peer_groups(conn):
    """
    Return peer groups.

    Expected peer_groups structure:
        company_id
        peer_group_name

    The function also supports:
        company_id
        peer_group
    """

    if not table_exists(conn, "peer_groups"):
        raise RuntimeError("Table 'peer_groups' does not exist.")

    columns = get_columns(conn, "peer_groups")

    if "company_id" not in columns:
        raise RuntimeError(
            "peer_groups table does not contain 'company_id'."
        )

    if "peer_group_name" in columns:
        group_column = "peer_group_name"
    elif "peer_group" in columns:
        group_column = "peer_group"
    else:
        raise RuntimeError(
            "peer_groups table does not contain "
            "'peer_group_name' or 'peer_group'."
        )

    rows = conn.execute(
        f"""
        SELECT company_id, {group_column}
        FROM peer_groups
        WHERE company_id IS NOT NULL
          AND {group_column} IS NOT NULL
        """
    ).fetchall()

    return rows


# ---------------------------------------------------------------------
# PERCENTILE CALCULATION
# ---------------------------------------------------------------------

def calculate_percentile_rank(values, target_value, lower_is_better=False):
    """
    Calculate percentile rank between 0 and 1.

    Example:
        0.00 = lowest
        0.25 = lower quartile
        0.50 = median
        0.75 = upper quartile
        1.00 = highest

    For metrics such as Debt/Equity, lower is better, so the ranking
    is reversed.
    """

    if not values:
        return None

    sorted_values = sorted(values)

    if target_value is None:
        return None

    n = len(sorted_values)

    if n == 1:
        return 1.0

    # Number of observations strictly below the target.
    below = sum(value < target_value for value in sorted_values)

    # Number of observations equal to the target.
    equal = sum(value == target_value for value in sorted_values)

    # Mid-rank percentile.
    rank = (below + (equal / 2)) / n

    if lower_is_better:
        rank = 1.0 - rank

    return round(rank, 4)


# ---------------------------------------------------------------------
# PEER PERCENTILE TABLE
# ---------------------------------------------------------------------

def create_peer_percentiles_table(conn):
    """Create the peer_percentiles table if it does not exist."""

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS peer_percentiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id TEXT NOT NULL,
            peer_group_name TEXT NOT NULL,
            metric TEXT NOT NULL,
            value REAL,
            percentile_rank REAL,
            year TEXT
        )
        """
    )

    conn.commit()


# ---------------------------------------------------------------------
# FINANCIAL DATA
# ---------------------------------------------------------------------

def get_financial_data(conn):
    """
    Read the required financial metrics from financial_ratios.

    Returns:
        List of dictionaries.
    """

    if not table_exists(conn, "financial_ratios"):
        raise RuntimeError(
            "Table 'financial_ratios' does not exist."
        )

    columns = get_columns(conn, "financial_ratios")

    required_columns = [
        "company_id",
        "year",
    ]

    for column in required_columns:
        if column not in columns:
            raise RuntimeError(
                f"financial_ratios table does not contain '{column}'."
            )

    available_metrics = {
        metric: column
        for metric, column in METRIC_COLUMNS.items()
        if column in columns
    }

    if not available_metrics:
        raise RuntimeError(
            "None of the configured peer-analysis metrics "
            "were found in financial_ratios."
        )

    select_columns = [
        "company_id",
        "year",
    ]

    select_columns.extend(
        available_metrics.values()
    )

    sql = f"""
        SELECT {", ".join(select_columns)}
        FROM financial_ratios
        WHERE company_id IS NOT NULL
        ORDER BY company_id, year DESC
    """

    rows = conn.execute(sql).fetchall()

    results = []

    for row in rows:
        record = {
            "company_id": row[0],
            "year": row[1],
        }

        for index, metric in enumerate(available_metrics):
            record[metric] = row[index + 2]

        results.append(record)

    return results


# ---------------------------------------------------------------------
# BUILD PEER DATA
# ---------------------------------------------------------------------

def build_peer_data(conn):
    """
    Combine peer groups with financial ratio data.

    Returns:
        {
            peer_group_name: [
                {
                    company_id,
                    year,
                    metric values...
                }
            ]
        }
    """

    peer_groups = get_peer_groups(conn)
    financial_data = get_financial_data(conn)

    company_to_group = {}

    for company_id, group_name in peer_groups:
        company_to_group[str(company_id)] = group_name

    grouped_data = {}

    for record in financial_data:
        company_id = str(record["company_id"])

        if company_id not in company_to_group:
            continue

        group_name = company_to_group[company_id]

        if group_name not in grouped_data:
            grouped_data[group_name] = []

        grouped_data[group_name].append(record)

    return grouped_data


# ---------------------------------------------------------------------
# GENERATE PERCENTILES
# ---------------------------------------------------------------------

def generate_peer_percentiles(conn):
    """
    Calculate percentile rankings for all peer groups and metrics.
    """

    create_peer_percentiles_table(conn)

    grouped_data = build_peer_data(conn)

    # Remove old generated values so the table always represents the
    # current financial_ratios data.
    conn.execute("DELETE FROM peer_percentiles")

    inserted = 0

    for peer_group_name, records in grouped_data.items():

        for metric in METRIC_COLUMNS:

            metric_records = [
                record
                for record in records
                if metric in record
                and record[metric] is not None
            ]

            if not metric_records:
                continue

            values = [
                float(record[metric])
                for record in metric_records
            ]

            lower_is_better = metric in LOWER_IS_BETTER

            for record in metric_records:

                value = float(record[metric])

                percentile = calculate_percentile_rank(
                    values=values,
                    target_value=value,
                    lower_is_better=lower_is_better,
                )

                conn.execute(
                    """
                    INSERT INTO peer_percentiles (
                        company_id,
                        peer_group_name,
                        metric,
                        value,
                        percentile_rank,
                        year
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record["company_id"],
                        peer_group_name,
                        metric,
                        value,
                        percentile,
                        record["year"],
                    ),
                )

                inserted += 1

    conn.commit()

    return inserted


# ---------------------------------------------------------------------
# QUERY FUNCTIONS
# ---------------------------------------------------------------------

def get_peer_ranking(
    peer_group_name: str,
    metric: str,
    db_path: Optional[Path] = None,
):
    """
    Get companies ranked within a peer group for a metric.

    Example:
        get_peer_ranking("IT Services", "roe")
    """

    if metric not in METRIC_COLUMNS:
        raise ValueError(
            f"Unknown metric '{metric}'. "
            f"Available metrics: {', '.join(METRIC_COLUMNS)}"
        )

    conn = get_connection(db_path)

    try:
        if not table_exists(conn, "peer_percentiles"):
            return []

        rows = conn.execute(
            """
            SELECT
                company_id,
                value,
                percentile_rank,
                year
            FROM peer_percentiles
            WHERE peer_group_name = ?
              AND metric = ?
            ORDER BY value DESC
            """,
            (
                peer_group_name,
                metric,
            ),
        ).fetchall()

        return rows

    finally:
        conn.close()


def get_company_peer_percentiles(
    company_id: str,
    db_path: Optional[Path] = None,
):
    """Return all peer percentile metrics for a company."""

    conn = get_connection(db_path)

    try:
        if not table_exists(conn, "peer_percentiles"):
            return []

        rows = conn.execute(
            """
            SELECT
                peer_group_name,
                metric,
                value,
                percentile_rank,
                year
            FROM peer_percentiles
            WHERE company_id = ?
            ORDER BY metric
            """,
            (company_id,),
        ).fetchall()

        return rows

    finally:
        conn.close()


# ---------------------------------------------------------------------
# SUMMARY
# ---------------------------------------------------------------------

def print_summary(conn):
    """Print a simple validation summary."""

    print("\n========== PEER ANALYSIS SUMMARY ==========")

    groups = conn.execute(
        """
        SELECT
            peer_group_name,
            COUNT(DISTINCT company_id)
        FROM peer_percentiles
        GROUP BY peer_group_name
        ORDER BY peer_group_name
        """
    ).fetchall()

    print(f"Peer groups: {len(groups)}")

    for group_name, company_count in groups:
        print(
            f"  {group_name}: "
            f"{company_count} companies"
        )

    metrics = conn.execute(
        """
        SELECT
            metric,
            COUNT(*)
        FROM peer_percentiles
        GROUP BY metric
        ORDER BY metric
        """
    ).fetchall()

    print(f"\nMetrics: {len(metrics)}")

    for metric, count in metrics:
        print(
            f"  {metric}: "
            f"{count} records"
        )

    total = conn.execute(
        """
        SELECT COUNT(*)
        FROM peer_percentiles
        """
    ).fetchone()[0]

    print(f"\nTotal percentile records: {total}")

    print("============================================\n")


# ---------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------

def main():
    """Run the complete peer analysis pipeline."""

    print("Starting Peer Analysis...")
    print(f"Database: {DB_PATH}")

    conn = get_connection()

    try:
        print("\nChecking database tables...")

        required_tables = [
            "financial_ratios",
            "peer_groups",
        ]

        for table in required_tables:
            if table_exists(conn, table):
                print(f"  ✓ {table}")
            else:
                print(f"  ✗ {table} NOT FOUND")
                raise RuntimeError(
                    f"Required table '{table}' does not exist."
                )

        print("\nGenerating peer percentile rankings...")

        inserted = generate_peer_percentiles(conn)

        print(
            f"✓ Inserted {inserted} percentile records."
        )

        print_summary(conn)

        # -------------------------------------------------------------
        # Example validation: IT Services / ROE
        # -------------------------------------------------------------

        print("========== IT SERVICES / ROE ==========")

        rows = conn.execute(
            """
            SELECT
                company_id,
                value,
                percentile_rank,
                year
            FROM peer_percentiles
            WHERE peer_group_name = ?
              AND metric = ?
            ORDER BY value DESC
            """,
            ("IT Services", "roe"),
        ).fetchall()

        if rows:
            for company_id, value, percentile, year in rows:
                print(
                    f"{company_id:10} | "
                    f"ROE: {value:10.4f} | "
                    f"Percentile: {percentile:6.4f} | "
                    f"Year: {year}"
                )
        else:
            print("No IT Services / ROE records found.")

        print("=======================================")

    finally:
        conn.close()

    print("\nPeer Analysis completed successfully.")


if __name__ == "__main__":
    main()