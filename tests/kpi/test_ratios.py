import pytest
from src.analytics.ratios import (
    net_profit_margin, operating_profit_margin, opm_crosscheck,
    return_on_equity, return_on_capital_employed, return_on_assets,
    debt_to_equity, high_leverage_flag, interest_coverage,
    interest_coverage_label, interest_warning, net_debt, asset_turnover,
    free_cash_flow, capex_intensity, fcf_conversion_rate,
    cfo_quality_score, cfo_quality_label, capital_allocation_pattern,
    book_value_per_share,
)
from src.analytics.cagr import cagr

# 8 profitability tests
def test_profitability_npm_normal_and_zero(): assert net_profit_margin(100,1000)==10 and net_profit_margin(100,0) is None
def test_profitability_opm_and_crosscheck(): 
    x=operating_profit_margin(200,1000); assert x==20 and opm_crosscheck(x,18,1)[0]
def test_profitability_roe_normal(): assert return_on_equity(100,20,80)==100
def test_profitability_roe_negative_equity(): assert return_on_equity(100,20,-30) is None
def test_profitability_roce(): assert return_on_capital_employed(150,50,100,50)==75
def test_profitability_roce_bad_denominator(): assert return_on_capital_employed(100,-50,10,20) is None
def test_profitability_roa_normal(): assert return_on_assets(100,500)==20
def test_profitability_roa_zero_assets(): assert return_on_assets(100,0) is None

# 8 leverage/efficiency tests
def test_debt_to_equity_debt_free_returns_zero(): assert debt_to_equity(0,10,20)==0
def test_debt_to_equity_negative_equity_returns_none(): assert debt_to_equity(10,10,-20) is None
def test_high_leverage_nonfinancial_flag(): assert high_leverage_flag(6,"Industrials") is True
def test_high_leverage_financials_suppressed(): assert high_leverage_flag(6,"Financials") is False
def test_icr_zero_interest_returns_none(): assert interest_coverage(100,20,0) is None
def test_icr_debt_free_label_and_warning(): assert interest_coverage_label(None)=="Debt Free" and interest_warning(1.2)
def test_net_debt_and_asset_turnover(): assert net_debt(100,40)==60 and asset_turnover(100,0) is None
def test_fcf_capex_and_conversion_guards(): assert free_cash_flow(10,-30)==-20 and capex_intensity(-50,1000)==5 and fcf_conversion_rate(10,0) is None

# 4 CAGR/cash-flow/allocation tests
def test_cagr_normal_and_zero_base(): assert round(cagr(100,121,2)[0],6)==10 and cagr(0,10,3)==(None,"ZERO_BASE")
def test_cagr_turnaround_decline_loss(): assert cagr(-10,20,3)==(None,"TURNAROUND") and cagr(20,-10,3)==(None,"DECLINE_TO_LOSS")
def test_cagr_both_negative_and_insufficient(): assert cagr(-20,-10,3)==(None,"BOTH_NEGATIVE") and cagr(10,20,0)==(None,"INSUFFICIENT")
def test_cash_quality_allocation_and_bvps(): 
    assert cfo_quality_score([1,2])==1.5 and cfo_quality_label(1.2)=="High Quality"
    assert capital_allocation_pattern(200,-100,-100,1.2)=="Shareholder Returns"
    assert book_value_per_share(20,80,10)==50
