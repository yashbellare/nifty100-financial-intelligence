PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS companies (
 id TEXT PRIMARY KEY, company_logo TEXT, company_name TEXT NOT NULL, chart_link TEXT, about_company TEXT,
 website TEXT, nse_profile TEXT, bse_profile TEXT, face_value REAL, book_value REAL,
 roce_percentage REAL, roe_percentage REAL
);
CREATE TABLE IF NOT EXISTS profitandloss (
 id INTEGER PRIMARY KEY, company_id TEXT NOT NULL, year TEXT NOT NULL, sales REAL, expenses REAL,
 operating_profit REAL, opm_percentage REAL, other_income REAL, interest REAL, depreciation REAL,
 profit_before_tax REAL, tax_percentage REAL, net_profit REAL, eps REAL, dividend_payout REAL,
 UNIQUE(company_id,year), FOREIGN KEY(company_id) REFERENCES companies(id)
);
CREATE TABLE IF NOT EXISTS balancesheet (
 id INTEGER PRIMARY KEY, company_id TEXT NOT NULL, year TEXT NOT NULL, equity_capital REAL, reserves REAL, borrowings REAL,
 other_liabilities REAL, total_liabilities REAL, fixed_assets REAL, cwip REAL, investments REAL, other_asset REAL, total_assets REAL,
 UNIQUE(company_id,year), FOREIGN KEY(company_id) REFERENCES companies(id)
);
CREATE TABLE IF NOT EXISTS cashflow (
 id INTEGER PRIMARY KEY, company_id TEXT NOT NULL, year TEXT NOT NULL, operating_activity REAL, investing_activity REAL, financing_activity REAL, net_cash_flow REAL,
 UNIQUE(company_id,year), FOREIGN KEY(company_id) REFERENCES companies(id)
);
CREATE TABLE IF NOT EXISTS analysis (
 id INTEGER PRIMARY KEY, company_id TEXT NOT NULL, compounded_sales_growth TEXT, compounded_profit_growth TEXT, stock_price_cagr TEXT, roe TEXT,
 FOREIGN KEY(company_id) REFERENCES companies(id)
);
CREATE TABLE IF NOT EXISTS documents (
 id INTEGER PRIMARY KEY, company_id TEXT NOT NULL, year INTEGER NOT NULL, annual_report TEXT,
 UNIQUE(company_id,year), FOREIGN KEY(company_id) REFERENCES companies(id)
);
CREATE TABLE IF NOT EXISTS prosandcons (
 id INTEGER PRIMARY KEY, company_id TEXT NOT NULL, pros TEXT, cons TEXT, FOREIGN KEY(company_id) REFERENCES companies(id)
);
CREATE TABLE IF NOT EXISTS sectors (
 id INTEGER PRIMARY KEY, company_id TEXT NOT NULL UNIQUE, broad_sector TEXT, sub_sector TEXT, index_weight_pct REAL, market_cap_category TEXT,
 FOREIGN KEY(company_id) REFERENCES companies(id)
);
CREATE TABLE IF NOT EXISTS stock_prices (
 id INTEGER PRIMARY KEY, company_id TEXT NOT NULL, date TEXT NOT NULL, open_price REAL, high_price REAL, low_price REAL, close_price REAL, volume INTEGER, adjusted_close REAL,
 UNIQUE(company_id,date), FOREIGN KEY(company_id) REFERENCES companies(id)
);
CREATE TABLE IF NOT EXISTS market_cap (
 id INTEGER PRIMARY KEY, company_id TEXT NOT NULL, year INTEGER NOT NULL, market_cap_crore REAL, enterprise_value_crore REAL, pe_ratio REAL, pb_ratio REAL, ev_ebitda REAL, dividend_yield_pct REAL,
 UNIQUE(company_id,year), FOREIGN KEY(company_id) REFERENCES companies(id)
);
CREATE TABLE IF NOT EXISTS financial_ratios (
 id INTEGER PRIMARY KEY, company_id TEXT NOT NULL, year TEXT NOT NULL,
 net_profit_margin_pct REAL, operating_profit_margin_pct REAL, return_on_equity_pct REAL, return_on_capital_employed_pct REAL, roce_sector_benchmark_pct REAL, roce_vs_sector_benchmark_pct REAL,
 return_on_assets_pct REAL, debt_to_equity REAL, high_leverage_flag INTEGER, interest_coverage REAL, icr_label TEXT, icr_warning_flag INTEGER,
 net_debt_cr REAL, asset_turnover REAL, free_cash_flow_cr REAL, capex_cr REAL, capex_intensity_pct REAL, capex_intensity_label TEXT,
 earnings_per_share REAL, book_value_per_share REAL, dividend_payout_ratio_pct REAL, total_debt_cr REAL, cash_from_operations_cr REAL,
 cfo_quality_score REAL, cfo_quality_label TEXT, fcf_conversion_rate_pct REAL, capital_allocation_pattern TEXT,
 revenue_cagr_3yr REAL, revenue_cagr_3yr_flag TEXT, revenue_cagr_5yr REAL, revenue_cagr_5yr_flag TEXT, revenue_cagr_10yr REAL, revenue_cagr_10yr_flag TEXT,
 pat_cagr_3yr REAL, pat_cagr_3yr_flag TEXT, pat_cagr_5yr REAL, pat_cagr_5yr_flag TEXT, pat_cagr_10yr REAL, pat_cagr_10yr_flag TEXT,
 eps_cagr_3yr REAL, eps_cagr_3yr_flag TEXT, eps_cagr_5yr REAL, eps_cagr_5yr_flag TEXT, eps_cagr_10yr REAL, eps_cagr_10yr_flag TEXT,
 composite_quality_score REAL,
 UNIQUE(company_id,year), FOREIGN KEY(company_id) REFERENCES companies(id)
);
CREATE TABLE IF NOT EXISTS peer_groups (
 id INTEGER PRIMARY KEY, peer_group_name TEXT NOT NULL, company_id TEXT NOT NULL, is_benchmark INTEGER NOT NULL DEFAULT 0,
 UNIQUE(peer_group_name,company_id), FOREIGN KEY(company_id) REFERENCES companies(id)
);
