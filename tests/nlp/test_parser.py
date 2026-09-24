import pandas as pd

from src.nlp.parser import cross_validate, parse_analysis_frame, parse_metric_value


def test_parse_metric_value_accepts_source_spacing_and_colon():
    assert parse_metric_value("10 Years: 21%") == (10, 21.0)
    assert parse_metric_value("5 Years          14%") == (5, 14.0)


def test_parse_analysis_frame_logs_unmatched_cells():
    frame = pd.DataFrame(
        {
            "company_id": ["abc"],
            "compounded_sales_growth": ["5 Years: 12%"],
            "compounded_profit_growth": ["not available"],
            "stock_price_cagr": ["3 Years: 8.5%"],
            "roe": [None],
        }
    )
    parsed, failures = parse_analysis_frame(frame)
    assert len(parsed) == 2
    assert set(failures["reason"]) == {"pattern_mismatch", "missing_value"}
    assert failures.iloc[0]["source_row"] == 3


def test_cross_validate_flags_divergence_above_five_percent():
    parsed = pd.DataFrame(
        [
            {
                "company_id": "ABC",
                "metric_type": "revenue_cagr",
                "period_years": 5,
                "value_pct": 20.0,
            }
        ]
    )
    ratios = pd.DataFrame([{"company_id": "ABC", "revenue_cagr_5yr": 12.0}])
    result = cross_validate(parsed, ratios)
    assert result.iloc[0]["status"] == "MANUAL_REVIEW"
    assert result.iloc[0]["divergence_pct"] == 8.0
