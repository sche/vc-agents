.PHONY: help install install-dev setup db-create db-migrate db-reset test lint format clean run-deals run-crawler run-enricher run-pipeline

# Default target
help:
	@echo "Available commands:"
	@echo "  make install        - Install production dependencies"
	@echo "  make install-dev    - Install all dependencies including dev tools"
	@echo "  make setup          - Complete setup (venv, deps, db, playwright)"
	@echo "  make db-create      - Create PostgreSQL database"
	@echo "  make db-schema      - Apply database schema"
	@echo "  make db-reset       - Drop and recreate database (⚠️  destructive)"
	@echo "  make test           - Run test suite"
	@echo "  make lint           - Run linters (ruff, mypy)"
	@echo "  make format         - Format code (black, ruff)"
	@echo "  make clean          - Remove cache and temp files"
	@echo "  make run-deals      - Run deals ingestor agent"
	@echo "  make run-crawler    - Run VC crawler agent"
	@echo "  make run-enricher   - Run social enricher agent"
	@echo "  make run-pipeline   - Run full pipeline"

# Installation
install:
	pip install -e .

install-dev:
	pip install -e ".[dev]"
	playwright install chromium

# Complete setup
setup: install-dev db-create db-schema
	@echo "✅ Setup complete!"
	@echo "Don't forget to configure your .env file"

# Verify setup
verify:
	python scripts/verify_setup.py

# Database operations
db-create:
	createdb vc_agents || echo "Database might already exist"

db-schema:
	psql vc_agents < db/schema.sql

db-reset:
	@echo "⚠️  This will DELETE all data. Press Ctrl+C to cancel, Enter to continue..."
	@read -r confirm
	dropdb vc_agents || true
	createdb vc_agents
	psql vc_agents < db/schema.sql
	@echo "✅ Database reset complete"

# Testing
test:
	pytest -v --cov=src --cov-report=term-missing

test-fast:
	pytest -v -x --ff

# Code quality
lint:
	@echo "Running ruff..."
	ruff check src/ tests/
	@echo "Running mypy..."
	mypy src/

format:
	@echo "Formatting with black..."
	black src/ tests/
	@echo "Fixing with ruff..."
	ruff check --fix src/ tests/

# Cleanup
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	rm -rf htmlcov/ .coverage

# Run agents (examples - update paths as needed)
run-deals:
	python -m src.agents.deals_ingestor

run-crawler:
	python -m src.agents.vc_crawler

run-enricher:
	python -m src.agents.social_enricher

run-intro:
	python -m src.agents.intro_personalizer

run-pipeline:
	python -m src.run_pipeline

# Development helpers
shell:
	ipython

check: format lint test
	@echo "✅ All checks passed!"
