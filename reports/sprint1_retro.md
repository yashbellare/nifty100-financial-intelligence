# Sprint 1 Retrospective

## Completed
- Environment/project structure created.
- 12 source datasets ingested (7 core + 5 supplementary).
- Tickers/year labels normalized.
- DQ-01 through DQ-16 implemented.
- Duplicate annual keys deduplicated before SQLite load.
- SQLite schema created with foreign keys enabled.
- Load audit, validation failures, deduplication log and exploratory SQL generated.
- 35+ ETL/DQ tests included.

## Source-spec note
The supplied specification alternates between "10 tables" and a concrete 12-table catalogue. This implementation follows the concrete dataset catalogue and deliverable list: companies, profitandloss, balancesheet, cashflow, analysis, documents, prosandcons, sectors, stock_prices, market_cap, financial_ratios, peer_groups.

## DQ-13 note
URL validation is implemented but disabled by default because the build environment has no outbound network access. Set `DQ_URL_CHECK=true` in `.env` to run HTTP HEAD checks in a network-enabled environment.

## Manual review
`output/manual_review_results.csv` records a deterministic 5-company manual review across P&L, Balance Sheet and Cash Flow; the reviewed records passed the defined coverage/balance checks.
