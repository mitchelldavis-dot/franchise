.PHONY: help install dev test ingest score export clean run-api run-ui run-all demo

help:
	@echo "Franchise Radar - Available Commands"
	@echo "===================================="
	@echo "make install      - Install dependencies"
	@echo "make dev          - Install dev dependencies"
	@echo "make test         - Run tests"
	@echo "make ingest       - Run default ingestion"
	@echo "make score        - Run scoring on all leads"
	@echo "make export       - Export leads to CSV"
	@echo "make run-api      - Run API server"
	@echo "make run-ui       - Run UI server"
	@echo "make run-all      - Run API + UI"
	@echo "make demo         - Run demo with mock data"
	@echo "make clean        - Clean temporary files"

install:
	pip install -e .

dev:
	pip install -e ".[dev]"

test:
	pytest tests/ -v --cov=src/franchise_radar --cov-report=html

ingest:
	python -m franchise_radar.cli ingest --source reddit --since 24h
	python -m franchise_radar.cli ingest --source rss
	python -m franchise_radar.cli score --type all

score:
	python -m franchise_radar.cli score --type all

export:
	python -m franchise_radar.cli export --format csv --out data/leads.csv

run-api:
	uvicorn franchise_radar.api.app:app --reload --host 0.0.0.0 --port 8000

run-ui:
	uvicorn franchise_radar.api.app:app --reload --host 0.0.0.0 --port 8000

run-all: run-api

demo:
	ENABLE_DEMO_MODE=true python -m franchise_radar.cli demo

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf .pytest_cache htmlcov .coverage

format:
	black src/ tests/
	ruff check src/ tests/ --fix

lint:
	black src/ tests/ --check
	ruff check src/ tests/
	mypy src/
