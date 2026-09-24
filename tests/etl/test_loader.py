from pathlib import Path

import pytest

from src.etl.loader import RAW, SUP, clean_df, read_excel

CORE_FILES = [
    ("companies", RAW / "companies.xlsx", True, "id"),
    ("profitandloss", RAW / "profitandloss.xlsx", True, "company_id"),
    ("balancesheet", RAW / "balancesheet.xlsx", True, "company_id"),
    ("cashflow", RAW / "cashflow.xlsx", True, "company_id"),
    ("analysis", RAW / "analysis.xlsx", True, "company_id"),
    ("documents", RAW / "documents.xlsx", True, "company_id"),
    ("prosandcons", RAW / "prosandcons.xlsx", True, "company_id"),
]

SUPPORTING_FILES = [
    ("sectors", SUP / "sectors.xlsx", False, "company_id"),
    ("stock_prices", SUP / "stock_prices.xlsx", False, "company_id"),
    ("market_cap", SUP / "market_cap.xlsx", False, "company_id"),
    ("financial_ratios", SUP / "financial_ratios.xlsx", False, "company_id"),
    ("peer_groups", SUP / "peer_groups.xlsx", False, "company_id"),
]


@pytest.mark.parametrize("name,path,core,key", CORE_FILES + SUPPORTING_FILES)
def test_loader_source_exists_and_has_rows(
    name: str, path: Path, core: bool, key: str
) -> None:
    frame = clean_df(name, read_excel(path, core_file=core))
    assert path.exists()
    assert not frame.empty
    assert key in frame.columns


@pytest.mark.parametrize("name,path,core,key", CORE_FILES + SUPPORTING_FILES)
def test_loader_source_has_unique_normalized_key_column(
    name: str, path: Path, core: bool, key: str
) -> None:
    frame = clean_df(name, read_excel(path, core_file=core))
    assert frame[key].notna().any()
    if key == "company_id":
        assert (
            frame[key].dropna().astype(str)
            == frame[key].dropna().astype(str).str.upper()
        ).all()


def test_loader_core_and_supporting_file_sets_are_complete() -> None:
    assert {item[0] for item in CORE_FILES} == {
        "companies",
        "profitandloss",
        "balancesheet",
        "cashflow",
        "analysis",
        "documents",
        "prosandcons",
    }
    assert {item[0] for item in SUPPORTING_FILES} == {
        "sectors",
        "stock_prices",
        "market_cap",
        "financial_ratios",
        "peer_groups",
    }
