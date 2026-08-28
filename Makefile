PYTHON?=python

load:
	$(PYTHON) -m src.etl.loader
ratios:
	$(PYTHON) scripts/populate_ratios.py
test:
	pytest -q
report:
	@echo "Sprint 2 reports are in output/"
dashboard:
	@echo "Sprint 5 target"
api:
	@echo "Sprint 6 target"
clean:
	rm -f nifty100.db output/*.csv output/*.log
