"""Peer-group radar chart generation for Sprint 3 Day 19."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


DB_PATH = Path("nifty100.db")
OUTPUT_DIR = Path("reports/radar_charts")

# Required 8 radar axes
RADAR_METRICS = {
    "ROE": "roe",
    "ROCE": "roce",
    "NPM": "npm",
    "D/E": "de",
    "FCF": "fcf",
    "PAT CAGR 5yr": "pat_cagr_5yr",
    "Revenue CAGR 5yr": "revenue_cagr_5yr",
    "Composite Score": "composite_score",
}


def load_peer_data(db_path: str | Path) -> pd.DataFrame:
    """Load latest company metrics and peer-group assignments."""

    conn = sqlite3.connect(db_path)

    query = """
        SELECT
            fr.company_id,
            fr.year,
            fr.return_on_equity_pct AS roe,
            fr.return_on_capital_employed_pct AS roce,
            fr.net_profit_margin_pct AS npm,
            fr.debt_to_equity AS de,
            fr.free_cash_flow_cr AS fcf,
            fr.pat_cagr_5yr,
            fr.revenue_cagr_5yr,
            pg.peer_group_name
        FROM financial_ratios fr
        LEFT JOIN peer_groups pg
            ON fr.company_id = pg.company_id
        WHERE fr.year = (
            SELECT MAX(fr2.year)
            FROM financial_ratios fr2
            WHERE fr2.company_id = fr.company_id
        )
    """

    df = pd.read_sql_query(query, conn)
    conn.close()

    return df


def load_composite_scores(
    db_path: str | Path,
) -> pd.DataFrame:
    """Load composite scores if the screener table exists."""

    conn = sqlite3.connect(db_path)

    tables = pd.read_sql_query(
        """
        SELECT name
        FROM sqlite_master
        WHERE type='table'
        """,
        conn,
    )

    if "financial_ratios" not in tables["name"].values:
        conn.close()
        return pd.DataFrame(columns=["company_id", "composite_score"])

    # Check available columns.
    columns = pd.read_sql_query(
        "PRAGMA table_info(financial_ratios)",
        conn,
    )

    column_names = set(columns["name"].tolist())

    if "composite_quality_score" in column_names:
        query = """
            SELECT
                company_id,
                composite_quality_score AS composite_score
            FROM financial_ratios
        """
        result = pd.read_sql_query(query, conn)

    elif "composite_score" in column_names:
        query = """
            SELECT
                company_id,
                composite_score
            FROM financial_ratios
        """
        result = pd.read_sql_query(query, conn)

    else:
        result = pd.DataFrame(
            columns=["company_id", "composite_score"]
        )

    conn.close()

    return result


def prepare_data(
    db_path: str | Path = DB_PATH,
) -> pd.DataFrame:
    """Load and prepare data for radar charts."""

    df = load_peer_data(db_path)

    scores = load_composite_scores(db_path)

    if not scores.empty:
        df = df.merge(
            scores,
            on="company_id",
            how="left",
        )
    else:
        df["composite_score"] = np.nan

    return df


def scale_for_radar(
    values: pd.Series,
    lower_better: bool = False,
) -> np.ndarray:
    """
    Convert raw metric values into a 0-100 radar score.

    Higher values are normally better.
    D/E is inverted because lower leverage is better.
    """

    numeric = pd.to_numeric(values, errors="coerce")

    if numeric.notna().sum() == 0:
        return np.zeros(len(values))

    low = numeric.min()
    high = numeric.max()

    if high == low:
        result = np.full(len(values), 50.0)
    else:
        result = ((numeric - low) / (high - low)) * 100

    if lower_better:
        result = 100 - result

    return result.fillna(0).to_numpy()


def build_radar_values(
    company: pd.Series,
    peers: pd.DataFrame,
) -> tuple[np.ndarray, np.ndarray]:
    """Build company and peer-average radar values."""

    company_values = []
    peer_values = []

    for label, column in RADAR_METRICS.items():

        lower_better = label == "D/E"

        combined = pd.concat(
            [
                peers[column],
                pd.Series([company[column]]),
            ],
            ignore_index=True,
        )

        scaled = scale_for_radar(
            combined,
            lower_better=lower_better,
        )

        company_values.append(scaled[-1])

        peer_values.append(
            np.mean(scaled[:-1])
            if len(scaled) > 1
            else 0
        )

    return (
        np.array(company_values),
        np.array(peer_values),
    )


def generate_radar_chart(
    company: pd.Series,
    peers: pd.DataFrame,
    output_path: Path,
) -> None:
    """Generate and save one radar chart."""

    labels = list(RADAR_METRICS.keys())

    company_values, peer_values = build_radar_values(
        company,
        peers,
    )

    num_axes = len(labels)

    angles = np.linspace(
        0,
        2 * np.pi,
        num_axes,
        endpoint=False,
    ).tolist()

    # Close polygons.
    company_values = np.concatenate(
        [company_values, [company_values[0]]]
    )

    peer_values = np.concatenate(
        [peer_values, [peer_values[0]]]
    )

    angles += angles[:1]

    fig, ax = plt.subplots(
        figsize=(8, 8),
        subplot_kw={"polar": True},
    )

    ax.plot(
        angles,
        company_values,
        linewidth=2,
        label=str(company["company_id"]),
    )

    ax.fill(
        angles,
        company_values,
        alpha=0.20,
    )

    ax.plot(
        angles,
        peer_values,
        linestyle="--",
        linewidth=2,
        label="Peer Average",
    )

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(
        labels,
        fontsize=10,
    )

    ax.set_ylim(0, 100)

    ax.set_yticks([20, 40, 60, 80, 100])
    ax.set_yticklabels(
        ["20", "40", "60", "80", "100"],
        fontsize=8,
    )

    peer_group = company.get(
        "peer_group_name",
        "No Peer Group",
    )

    ax.set_title(
        f"{company['company_id']} — {peer_group}\n"
        "Peer Comparison Radar",
        fontsize=14,
        pad=25,
    )

    ax.legend(
        loc="upper right",
        bbox_to_anchor=(1.25, 1.10),
    )

    fig.tight_layout()

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    fig.savefig(
        output_path,
        dpi=150,
        bbox_inches="tight",
    )

    plt.close(fig)


def generate_all_radar_charts(
    db_path: str | Path = DB_PATH,
    output_dir: str | Path = OUTPUT_DIR,
) -> int:
    """Generate radar charts for all companies with peer groups."""

    output_dir = Path(output_dir)

    df = prepare_data(db_path)

    if df.empty:
        print("No financial data found.")
        return 0

    assigned = df[
        df["peer_group_name"].notna()
    ].copy()

    if assigned.empty:
        print("No companies have peer groups assigned.")
        return 0

    generated = 0

    for _, company in assigned.iterrows():

        peer_group = company["peer_group_name"]

        peers = assigned[
            assigned["peer_group_name"] == peer_group
        ].copy()

        filename = (
            f"{company['company_id']}_radar.png"
        )

        output_path = output_dir / filename

        generate_radar_chart(
            company,
            peers,
            output_path,
        )

        generated += 1

        print(
            f"✓ {company['company_id']} "
            f"({peer_group}) -> {output_path}"
        )

    return generated


def main() -> None:
    """Run Day 19 radar-chart generation."""

    print("Starting Radar Chart Generation...")
    print(f"Database: {Path(DB_PATH).resolve()}")
    print(f"Output:   {Path(OUTPUT_DIR).resolve()}")
    print()

    count = generate_all_radar_charts()

    print()
    print("=" * 45)
    print("RADAR CHART SUMMARY")
    print("=" * 45)
    print(f"Charts generated: {count}")
    print(f"Output directory: {OUTPUT_DIR}")
    print("=" * 45)


if __name__ == "__main__":
    main()