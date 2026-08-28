# Sprint 2 — Financial Ratio Engine Status

## Definition of Done

- `financial_ratios`: **1,155 company-year rows** across all **92 companies**.
- Ratio table contains **48 computed/flag columns** plus the primary key.
- Required KPI columns are populated with at least one non-null value; no KPI column is null-only.
- Capital allocation output: `output/capital_allocation.csv` with 1,056 company-year cash-flow rows.
- Edge-case log: `output/ratio_edge_cases.log` with every anomaly categorized as data source issue, version difference, or formula discrepancy.
- KPI formula tests: **20 passed** in `tests/kpi/test_ratios.py`.
- Full project test suite: **81 passed**.
- Manual ROE and 5-year revenue CAGR spot-check for ABB, TCS and HDFCBANK matched database values within 0.1 percentage points.
- Screener preview using the 2024-03 annual cohort: **37 companies** satisfy ROE > 15% and D/E < 1, within the required 15–50 range.

## Formula decisions

- ROE = PAT / (equity capital + reserves) × 100; non-positive equity base returns NULL.
- ROCE = EBIT / (equity + reserves + borrowings) × 100.
- Financials ROCE is also stored relative to the same-year Financials peer median; D/E high-leverage warnings are suppressed for Financials.
- D/E returns 0 for debt-free companies.
- ICR returns NULL when interest is zero and stores `Debt Free` in `icr_label`.
- FCF = CFO + CFI; negative FCF is valid.
- CapEx is represented as absolute investing cash flow for intensity/capex amount.
- CAGR uses the latest observation and the closest observation at least N years earlier; all six requested edge-case flags are explicit.
- BVPS uses `(equity + reserves) / equity capital × face value`.
- Composite quality score is a transparent 0–100 score using available ROE, OPM, D/E, ICR and CFO-quality components; its exact weighting is documented in `scripts/populate_ratios.py`.

## Outputs

- `nifty100.db`
- `output/capital_allocation.csv`
- `output/ratio_edge_cases.log`
- `reports/sprint2_status.md`
- `src/analytics/ratios.py`
- `src/analytics/cagr.py`
- `src/analytics/cashflow_kpis.py`
- `tests/kpi/test_ratios.py`
