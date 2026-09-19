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
	@echo "Sprint 6 target"
clean:
	rm -f nifty100.db output/*.csv output/*.log
