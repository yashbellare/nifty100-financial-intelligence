PYTHON?=python

load:
	$(PYTHON) -m src.etl.loader
ratios:
	@echo "Sprint 2 target: ratio engine not implemented in Sprint 1"
test:
	pytest -q
report:
	@echo "Sprint 1 reports are in output/"
dashboard:
	@echo "Sprint 5 target"
api:
	@echo "Sprint 6 target"
clean:
	rm -f nifty100.db output/*.csv output/*.log
