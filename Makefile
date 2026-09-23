PYTHON?=python

load:
	$(PYTHON) -m src.etl.loader
ratios:
	$(PYTHON) scripts/populate_ratios.py
valuation:
	$(PYTHON) -m src.analytics.valuation
test:
	pytest -q
report:
	$(PYTHON) -m src.reports.batch_reports
sprint5:
	$(PYTHON) -m src.nlp.parser
	$(PYTHON) -m src.nlp.pros_cons_generator
	$(PYTHON) -m src.analytics.cashflow_kpis
	$(PYTHON) -m src.reports.batch_reports
dashboard:
	$(PYTHON) -m streamlit run src/dashboard/app.py --server.port 8501
api:
	$(PYTHON) -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000
clean:
	rm -f nifty100.db output/*.csv output/*.log
