"""KMeans financial archetype clustering for the Nifty 100 universe."""
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

from .cagr import cagr_from_series


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = PROJECT_ROOT / "nifty100.db"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "output"
DEFAULT_REPORTS_DIR = PROJECT_ROOT / "reports"

FEATURE_COLUMNS = [
	"return_on_equity_pct",
	"debt_to_equity",
	"revenue_cagr_5yr",
	"fcf_cagr_5yr",
	"operating_profit_margin_pct",
]
OUTPUT_COLUMNS = ["company_id", "cluster_id", "cluster_name", "distance_from_centroid"]


def load_clustering_data(db_path: Path = DEFAULT_DB_PATH) -> pd.DataFrame:
	"""Load the latest ratio and sector row for every company."""
	with sqlite3.connect(db_path) as connection:
		companies = pd.read_sql_query(
			"SELECT id AS company_id FROM companies", connection
		)
		ratios = pd.read_sql_query("SELECT * FROM financial_ratios", connection)
		sectors = pd.read_sql_query(
			"SELECT company_id, broad_sector FROM sectors", connection
		)

	if ratios.empty:
		raise ValueError("financial_ratios contains no rows")
	missing_columns = set(FEATURE_COLUMNS) - set(ratios.columns) - {"fcf_cagr_5yr"}
	if missing_columns:
		raise ValueError(f"financial_ratios is missing columns: {sorted(missing_columns)}")
	if "fcf_cagr_5yr" not in ratios.columns:
		ratios["year_number"] = pd.to_numeric(
			ratios["year"].astype(str).str.extract(r"(\d{4})", expand=False),
			errors="coerce",
		)
		fcf_cagrs = {}
		for company_id, rows in ratios.dropna(subset=["year_number"]).groupby("company_id"):
			series = rows[["year_number", "free_cash_flow_cr"]].dropna()
			fcf_cagrs[company_id] = cagr_from_series(
				list(zip(series["year_number"], series["free_cash_flow_cr"])), 5
			)[0]
		ratios["fcf_cagr_5yr"] = ratios["company_id"].map(fcf_cagrs)
		ratios = ratios.drop(columns="year_number")

	ratios["year_sort"] = pd.to_numeric(
		ratios["year"].astype(str).str.extract(r"(\d{4})(?:-(\d{1,2}))?", expand=False)[0],
		errors="coerce",
	)
	ratios = ratios.sort_values(["company_id", "year_sort", "year"])
	ratios = ratios.drop_duplicates("company_id", keep="last").drop(columns="year_sort")
	result = companies.merge(ratios, on="company_id", how="left").merge(
		sectors, on="company_id", how="left"
	)
	if result[FEATURE_COLUMNS].notna().any(axis=1).sum() == 0:
		raise ValueError("No usable clustering features found")
	return result


def impute_by_sector(
	data: pd.DataFrame, feature_columns: list[str] = FEATURE_COLUMNS
) -> pd.DataFrame:
	"""Impute each feature with its sector median, then its global median."""
	result = data.copy()
	if "broad_sector" not in result:
		result["broad_sector"] = "Unknown"
	result["broad_sector"] = result["broad_sector"].fillna("Unknown").astype(str)
	for column in feature_columns:
		result[column] = pd.to_numeric(result[column], errors="coerce")
		sector_medians = result.groupby("broad_sector")[column].transform("median")
		global_median = result[column].median()
		if pd.isna(global_median):
			global_median = 0.0
		result[column] = result[column].fillna(sector_medians).fillna(global_median)
	return result


def _cluster_names(centers: pd.DataFrame) -> dict[int, str]:
	"""Assign stable descriptive archetype names from cluster feature profiles."""
	profile = centers.copy()
	for column in FEATURE_COLUMNS:
		values = profile[column]
		spread = values.max() - values.min()
		profile[f"_{column}"] = (values - values.min()) / spread if spread else 0.5

	profile["_quality"] = (
		profile["_return_on_equity_pct"]
		+ profile["_operating_profit_margin_pct"]
		+ profile["_revenue_cagr_5yr"]
		+ profile["_fcf_cagr_5yr"]
		- profile["_debt_to_equity"]
	)
	profile["_growth"] = profile["_revenue_cagr_5yr"] + profile["_fcf_cagr_5yr"]
	profile["_defensive"] = (
		profile["_return_on_equity_pct"]
		+ profile["_operating_profit_margin_pct"]
		- profile["_debt_to_equity"]
	)
	profile["_distress"] = (
		profile["_debt_to_equity"]
		- profile["_return_on_equity_pct"]
		- profile["_operating_profit_margin_pct"]
		- profile["_growth"]
	)

	roles = [
		("Distressed or Turnaround", "_distress", True),
		("High-Quality Compounders", "_quality", True),
		("Emerging Growth", "_growth", True),
		("Defensive Dividend Payers", "_defensive", True),
	]
	remaining = set(profile.index)
	names: dict[int, str] = {}
	for name, score, descending in roles:
		ordered = profile.loc[list(remaining), score].sort_values(ascending=not descending)
		if not ordered.empty:
			cluster_id = int(ordered.index[0])
			names[cluster_id] = name
			remaining.remove(cluster_id)
	for cluster_id in remaining:
		names[int(cluster_id)] = "Value Cyclicals"
	return names


def fit_clusters(
	data: pd.DataFrame, n_clusters: int = 5, random_state: int = 42
) -> tuple[pd.DataFrame, KMeans, StandardScaler]:
	"""Fit scaled KMeans and return labels, model, and scaler."""
	if len(data) < n_clusters:
		raise ValueError(f"Need at least {n_clusters} companies, got {len(data)}")
	prepared = impute_by_sector(data)
	scaler = StandardScaler()
	scaled = scaler.fit_transform(prepared[FEATURE_COLUMNS])
	model = KMeans(n_clusters=n_clusters, random_state=random_state, n_init=20)
	cluster_ids = model.fit_predict(scaled)
	distances = model.transform(scaled).min(axis=1)
	centers = pd.DataFrame(
		scaler.inverse_transform(model.cluster_centers_), columns=FEATURE_COLUMNS
	)
	centers.index = range(n_clusters)
	names = _cluster_names(centers)
	labels = pd.DataFrame(
		{
			"company_id": prepared["company_id"].astype(str).values,
			"cluster_id": cluster_ids.astype(int),
			"cluster_name": [names[int(cluster_id)] for cluster_id in cluster_ids],
			"distance_from_centroid": distances.astype(float),
		}
	)
	return labels.sort_values("company_id").reset_index(drop=True), model, scaler


def _write_elbow_plot(
	data: pd.DataFrame,
	reports_dir: Path,
	random_state: int = 42,
) -> Path:
	"""Write inertia values for k=2..10 to the sprint elbow plot."""
	prepared = impute_by_sector(data)
	scaled = StandardScaler().fit_transform(prepared[FEATURE_COLUMNS])
	max_k = min(10, len(prepared) - 1)
	ks = list(range(2, max_k + 1))
	inertias = [
		KMeans(n_clusters=k, random_state=random_state, n_init=20).fit(scaled).inertia_
		for k in ks
	]
	reports_dir.mkdir(parents=True, exist_ok=True)
	path = reports_dir / "elbow_plot.png"
	fig, axis = plt.subplots(figsize=(8, 5))
	axis.plot(ks, inertias, marker="o")
	axis.axvline(5, color="tab:red", linestyle="--", label="Selected k=5")
	axis.set(title="KMeans Elbow Plot", xlabel="Number of clusters (k)", ylabel="Inertia")
	axis.legend()
	fig.tight_layout()
	fig.savefig(path, dpi=150)
	plt.close(fig)
	return path


def generate_clustering_outputs(
	db_path: Path = DEFAULT_DB_PATH,
	output_dir: Path = DEFAULT_OUTPUT_DIR,
	reports_dir: Path = DEFAULT_REPORTS_DIR,
) -> pd.DataFrame:
	"""Generate cluster labels and the KMeans elbow plot."""
	data = load_clustering_data(Path(db_path))
	labels, _, _ = fit_clusters(data)
	output_dir = Path(output_dir)
	output_dir.mkdir(parents=True, exist_ok=True)
	labels[OUTPUT_COLUMNS].to_csv(output_dir / "cluster_labels.csv", index=False)
	_write_elbow_plot(data, Path(reports_dir))
	return labels


def main() -> None:
	"""Generate Day 36 clustering artifacts from the project database."""
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
	parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
	parser.add_argument("--reports-dir", type=Path, default=DEFAULT_REPORTS_DIR)
	args = parser.parse_args()
	labels = generate_clustering_outputs(args.db, args.output_dir, args.reports_dir)
	print(f"Generated {len(labels)} cluster labels across {labels['cluster_id'].nunique()} clusters")


if __name__ == "__main__":
	main()