.PHONY: setup generate validate demo test clean

PYTHON ?= python3
UV ?= $(shell which uv 2>/dev/null || echo "")

setup:
	@if [ -n "$(UV)" ]; then \
		echo "Installing dependencies with uv..."; \
		$(UV) pip install -e . ; \
	else \
		echo "Installing dependencies with pip..."; \
		$(PYTHON) -m pip install -r requirements.txt ; \
	fi

generate:
	@echo "Generating room-level synthetic data from ASHRAE shapes..."
	@if [ -n "$(UV)" ]; then \
		$(UV) run python -m synthetic_data.cli generate ; \
	else \
		$(PYTHON) -m synthetic_data.cli generate ; \
	fi

validate:
	@echo "Validating synthetic output data..."
	@if [ -n "$(UV)" ]; then \
		$(UV) run python -m synthetic_data.cli validate ; \
	else \
		$(PYTHON) -m synthetic_data.cli validate ; \
	fi

test:
	@echo "Running tests..."
	@if [ -n "$(UV)" ]; then \
		$(UV) run pytest tests/ -v ; \
	else \
		$(PYTHON) -m pytest tests/ -v ; \
	fi

demo: generate validate
	@echo "Displaying demo sample summary..."
	@if [ -n "$(UV)" ]; then \
		$(UV) run python -m synthetic_data.cli summary ; \
	else \
		$(PYTHON) -m synthetic_data.cli summary ; \
	fi

clean:
	rm -rf output/*.parquet output/*.csv .pytest_cache *.egg-info build
