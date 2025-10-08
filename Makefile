.PHONY: help install install-dev setup db-create db-migrate db-reset test lint format clean run-deals run-crawler run-enricher run-pipeline

# Default target
help:
	@echo "Available commands:"
	@echo "  make install        - Install production dependencies"
	@echo "  make install-dev    - Install all dependencies including dev tools"
	@echo "  make setup          - Complete setup (venv, deps, db, playwright)"
	@echo "  make db-create      - Create PostgreSQL database (one-time)"
	@echo "  make db-init        - Initialize database schema from SQLAlchemy models"
	@echo "  make db-reset       - Drop and recreate database (⚠️  destructive)"
	@echo "  make test           - Run test suite"
	@echo "  make lint           - Run linters (ruff, mypy)"
	@echo "  make format         - Format code (black, ruff)"
	@echo "  make clean          - Remove cache and temp files"
	@echo "  make load-deals     - Load DefiLlama deals (simple script)"
	@echo "  make run-crawler    - Run VC crawler agent"
	@echo "  make run-enricher   - Run social enricher agent"
	@echo "  make run-pipeline   - Run full pipeline"
	@echo ""
	@echo "UI Commands:"
	@echo "  make retool-start   - Start Retool UI (http://localhost:3000)"
	@echo "  make retool-stop    - Stop Retool UI"
	@echo "  make retool-logs    - View Retool logs"

# Installation
install:
	pip install -e .

install-dev:
	pip install -e ".[dev]"
	playwright install chromium

# Complete setup
setup: install-dev db-init
	@echo "✅ Setup complete!"
	@echo "Don't forget to configure your .env file"

# Verify setup
verify:
	python scripts/verify_setup.py

# Database operations
db-create:
	createdb -U vc_user -h localhost vc_agents || echo "Database might already exist"

db-init:
	python -m src.db.init_db

db-reset:
	@echo "⚠️  This will DELETE all data. Press Ctrl+C to cancel, Enter to continue..."
	@read -r confirm
	python -m src.db.init_db --reset
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
load-deals:
	python scripts/load_defillama_deals.py

load-deals-limit:
	python scripts/load_defillama_deals.py --limit 10

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

# Retool UI
retool-start:
	@echo "🚀 Starting Retool..."
	docker compose -f docker-compose.retool.yml up -d
	@echo "✅ Retool is starting..."
	@echo "📍 Access at: http://localhost:3000"
	@echo "⏳ Wait ~30 seconds for Retool to be ready"
	@echo "📖 See docs/RETOOL_SETUP.md for connection instructions"

retool-stop:
	docker compose -f docker-compose.retool.yml down

retool-logs:
	docker logs -f retool

retool-restart:
	docker compose -f docker-compose.retool.yml restart
	@echo "✅ Retool restarted"
