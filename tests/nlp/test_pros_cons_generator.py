import pandas as pd

from src.nlp.pros_cons_generator import evaluate_company, generate_pros_cons


def _rows(**overrides):
    defaults = {
        "company_id": "TEST",
        "year": ["2020", "2021", "2022", "2023", "2024"],
        "return_on_equity_pct": [21, 22, 23, 24, 25],
        "free_cash_flow_cr": [10, 11, 12, 13, 14],
        "debt_to_equity": [0, 0, 0, 0, 0],
        "revenue_cagr_5yr": [20, 20, 20, 20, 20],
        "pat_cagr_5yr": [25, 25, 25, 25, 25],
        "eps_cagr_5yr": [18, 18, 18, 18, 18],
        "operating_profit_margin_pct": [26, 26, 26, 26, 26],
        "interest_coverage": [12, 12, 12, 12, 12],
        "dividend_yield_pct": [3, 3, 3, 3, 3],
        "dividend_payout_ratio_pct": [50, 50, 50, 50, 50],
        "return_on_capital_employed_pct": [15, 15, 15, 15, 15],
        "net_profit": [10, 10, 10, 10, 10],
        "net_debt_cr": [10, 10, 10, 10, 10],
        "operating_profit": [20, 20, 20, 20, 20],
        "depreciation": [2, 2, 2, 2, 2],
        "sales": [100, 110, 120, 130, 140],
        "total_assets": [100, 110, 120, 130, 140],
        "borrowings": [20, 19, 18, 17, 16],
        "broad_sector": ["Information Technology"] * 5,
    }
    defaults.update(overrides)
    return pd.DataFrame(defaults)


def test_evaluate_company_emits_explicit_pro_rules():
    result = pd.DataFrame(evaluate_company("TEST", _rows()))

    assert {"P01", "P02", "P03", "P04", "P05", "P06", "P07", "P08", "P09", "P10", "P11", "P12"}.issubset(
        set(result.loc[result["type"] == "pro", "rule_id"])
    )
    assert result["confidence_pct"].between(0, 100).all()


def test_generate_pros_cons_falls_back_to_both_types():
    sparse = pd.DataFrame({"company_id": ["A", "B"], "year": ["2024", "2024"]})

    result = generate_pros_cons(sparse)

    assert set(result["type"]) == {"pro", "con"}
    assert all(set(types) == {"pro", "con"} for types in result.groupby("company_id")["type"].agg(set))
    assert (result["confidence_pct"] > 60).all()


def test_evaluate_company_emits_debt_and_loss_cons():
    rows = _rows(
        debt_to_equity=[2.1] * 5,
        interest_coverage=[1.2] * 5,
        net_profit=[-1, 10, 10, 10, 10],
    )

    result = pd.DataFrame(evaluate_company("TEST", rows))

    assert {"C01", "C06"}.issubset(set(result.loc[result["type"] == "con", "rule_id"]))