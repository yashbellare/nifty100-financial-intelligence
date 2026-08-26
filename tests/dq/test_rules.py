import pandas as pd
from src.etl.validator import validate_all

def base():
 c=pd.DataFrame({"id":["TCS"],"company_name":["TCS"]})
 pl=pd.DataFrame({"company_id":["TCS"],"year":["2024-03"],"sales":[100],"expenses":[80],"operating_profit":[20],"opm_percentage":[20],"other_income":[0],"interest":[0],"depreciation":[0],"profit_before_tax":[20],"tax_percentage":[25],"net_profit":[15],"eps":[1],"dividend_payout":[20]})
 bs=pd.DataFrame({"company_id":["TCS"],"year":["2024-03"],"equity_capital":[10],"reserves":[90],"borrowings":[0],"other_liabilities":[0],"total_liabilities":[100],"fixed_assets":[50],"cwip":[0],"investments":[0],"other_asset":[50],"total_assets":[100]})
 cf=pd.DataFrame({"company_id":["TCS"],"year":["2024-03"],"operating_activity":[20],"investing_activity":[-5],"financing_activity":[-2],"net_cash_flow":[13]})
 return {"companies":c,"profitandloss":pl,"balancesheet":bs,"cashflow":cf,"analysis":pd.DataFrame(columns=["company_id"]),"documents":pd.DataFrame(columns=["company_id","Year","Annual_Report"]),"prosandcons":pd.DataFrame(columns=["company_id"]),"sectors":pd.DataFrame({"company_id":["TCS"],"sub_sector":["IT Services"]}),"stock_prices":pd.DataFrame(columns=["company_id"]),"market_cap":pd.DataFrame(columns=["company_id"]),"financial_ratios":pd.DataFrame(columns=["company_id"]),"peer_groups":pd.DataFrame(columns=["company_id"])}

def ids(f): return {x["rule_id"] for x in f}
def test_dq04_bs_balance():
 d=base(); d["balancesheet"].loc[0,"total_liabilities"]=1020; assert "DQ-04" in ids(validate_all(d))
def test_dq06_zero_sales():
 d=base(); d["profitandloss"].loc[0,"sales"]=0; assert "DQ-06" in ids(validate_all(d))
def test_dq09_cash_mismatch():
 d=base(); d["cashflow"].loc[0,"net_cash_flow"]=100; assert "DQ-09" in ids(validate_all(d))
def test_dq11_tax_range():
 d=base(); d["profitandloss"].loc[0,"tax_percentage"]=80; assert "DQ-11" in ids(validate_all(d))
def test_dq12_dividend_cap():
 d=base(); d["profitandloss"].loc[0,"dividend_payout"]=250; assert "DQ-12" in ids(validate_all(d))
def test_dq14_eps_sign():
 d=base(); d["profitandloss"].loc[0,"eps"]=-1; assert "DQ-14" in ids(validate_all(d))
def test_dq16_coverage():
 d=base(); assert "DQ-16" in ids(validate_all(d))
