# Nifty 100 Financial Intelligence Platform — Sprint 6

This package implements the Nifty 100 data foundation, financial ratio engine, valuation outputs, and an eight-screen Streamlit dashboard against the supplied project specification and 12 source datasets.

## Run
```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.template .env   # Windows
# cp .env.template .env   # macOS/Linux
make load
make test
```

The API and dashboard can run together in separate terminals:

```bash
make api                 # http://localhost:8000
make dashboard           # http://localhost:8501
```

## Dashboard

Generate the valuation outputs and start the dashboard with:

```bash
make valuation
streamlit run src/dashboard/app.py --server.port 8501
```

Open `http://localhost:8501`. The app uses cached shared loaders with a ten-minute TTL and safely displays `N/A` when a company has partial history.

### Screen guide

- **Home**: year-aware KPI tiles, sector mix, and the top five quality scores.
- **Company profile**: searchable company card, latest KPIs, financial history, ROE/ROCE trend, and pros/cons.
- **Screener**: live metric filters, six presets, result count, and CSV export.
- **Peer comparison**: peer-group selection, benchmark radar, and peer KPI table.
- **Trend analysis**: up to three metrics with year-over-year annotations.
- **Sector analysis**: revenue/ROE bubble chart and sector median KPIs.
- **Capital allocation**: interactive pattern treemap and company drill-down.
- **Annual reports**: report-year list with availability status and BSE links.

Valuation artifacts are written to `output/valuation_summary.xlsx` and `output/valuation_flags.csv`.

## API

Start the Day 38 FastAPI server with:

```bash
make api
# or: uvicorn src.api.main:app --host 0.0.0.0 --port 8000
```

The health check is available at `http://localhost:8000/api/v1/health` and the interactive OpenAPI documentation is at `http://localhost:8000/docs`.

Day 40 API artifacts are checked in at `docs/openapi.json` and `docs/postman_collection.json`. Example calls:

```bash
curl http://localhost:8000/api/v1/companies/TCS
curl "http://localhost:8000/api/v1/screener?min_roe=15&max_de=2"
curl http://localhost:8000/api/v1/companies/TCS/tearsheet --output TCS_tearsheet.pdf
```

Regenerate the API specifications with `python scripts/export_api_specs.py`.

## Testing And QA

```bash
python -m pytest tests -v
python -m pytest tests --html=reports/pytest_report.html --self-contained-html
python -m scripts.performance_check
```

The performance check writes `output/perf_notes.md`. It measures ten concurrent screener calls, five dashboard ratio loads, and applies the SQLite indexes from `db/schema.sql`.

## Analyst Guide

Generate the ten-page analyst guide with:

```bash
python scripts/generate_analyst_guide.py
```

The resulting PDF is written to `docs/analyst_guide.pdf`.

## Outputs
- `nifty100.db` — SQLite data foundation
- `output/load_audit.csv` — per-table input/output/rejections
- `output/validation_failures.csv` — DQ-01…DQ-16 findings with resolution status
- `output/deduplication_log.csv` — DQ-02/duplicate actions
- `notebooks/exploratory_queries.sql` — 11 exploratory queries
- `tests/` — 131+ automated tests

## Important specification reconciliation
The document says "10 tables" in a few places, but its dataset catalogue, schema output list and 12 source files identify 12 datasets/tables. Sprint 1 follows the explicit 12-table catalogue so no source dataset is silently dropped.

## DQ-13
URL checks are optional and disabled by default for offline environments.


## Sprint 2 — Financial Ratio Engine

Run the completed ratio engine with:

```bash
make ratios
make test
```

Sprint 2 generates `financial_ratios` for the union of all available P&L, balance-sheet and cash-flow company-years, `output/capital_allocation.csv`, `output/ratio_edge_cases.log`, a manual spot-check workbook, and a screener preview. See `reports/sprint2_status.md` for the completion evidence and formula decisions.
