# Nifty 100 Financial Intelligence Platform — Sprint 1

This package implements Sprint 1 Data Foundation against the supplied project specification and 12 source datasets.

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

## Outputs
- `nifty100.db` — SQLite data foundation
- `output/load_audit.csv` — per-table input/output/rejections
- `output/validation_failures.csv` — DQ-01…DQ-16 findings with resolution status
- `output/deduplication_log.csv` — DQ-02/duplicate actions
- `notebooks/exploratory_queries.sql` — 11 exploratory queries
- `tests/` — 35+ unit tests

## Important specification reconciliation
The document says "10 tables" in a few places, but its dataset catalogue, schema output list and 12 source files identify 12 datasets/tables. Sprint 1 follows the explicit 12-table catalogue so no source dataset is silently dropped.

## DQ-13
URL checks are optional and disabled by default for offline environments.
