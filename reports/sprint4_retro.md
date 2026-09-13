# Sprint 4 retrospective

## Delivered

- Eight-screen Streamlit dashboard available from `src/dashboard/app.py`.
- Shared cached data access for company, financial, sector, peer, market-cap, valuation, and report data.
- Screener presets, live filters, visible-column CSV export, and missing-data-safe rendering.
- Valuation summary workbook and filtered caution/discount CSV generated in `output/`.

## UX decisions

- Search fields narrow the company selectbox so a 92-company universe remains easy to scan.
- Plotly charts use responsive width and fixed heights to prevent page overflow.
- Partial histories remain visible and report the number of available years rather than failing the page.
- Missing numeric values display as `N/A`; unavailable report URLs receive a red status instead of a dead link.

## Data and performance notes

- Source workbooks contain internal row IDs in addition to company IDs; dashboard normalization drops only the surrogate row ID.
- Market-cap valuation fields are taken from the latest available year for each company.
- FCF yield is calculated as FCF divided by market cap in crore, multiplied by 100.
- Relative P/E flags use the latest-year positive sector median: above 150% is `Caution`, below 70% is `Discount`, otherwise `Fair`.
- Cached loaders use a 600-second TTL. The existing project suite passes 81 tests; valuation generation produced 92 company rows.

## Known operating notes

- Annual-report HTTP checks are intentionally short and cached because some source URLs are offline or unavailable.
- Start the application with `streamlit run src/dashboard/app.py --server.port 8501` after activating `.venv`.
