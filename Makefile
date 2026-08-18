.PHONY: help install install-dev sync sync-dev run test clean format check deps venv setup recreate-env

# Default target
help:
	@echo "Slack Repo Agent - Makefile Commands"
	@echo "======================================"
	@echo ""
	@echo "Setup:"
	@echo "  make setup       - Complete dev environment setup (venv + all deps)"
	@echo "  make install     - Install production dependencies only"
	@echo "  make install-dev - Install all dependencies including dev tools"
	@echo "  make sync        - Sync production dependencies with uv"
	@echo "  make sync-dev    - Sync all dependencies including dev tools"
	@echo "  make deps        - Check if dependencies are installed"
	@echo "  make recreate-env - Remove and recreate virtual environment with all deps"
	@echo ""
	@echo "Running:"
	@echo "  make run         - Run the bot"
	@echo ""
	@echo "Development:"
	@echo "  make test        - Run all tests"
	@echo "  make test-cov    - Run tests with coverage report"
	@echo "  make test-unit   - Run unit tests only"
	@echo "  make test-integration - Run integration tests only"
	@echo "  make test-verbose - Run tests with verbose output"
	@echo "  make test-coverage-html - Run tests and open HTML coverage report"
	@echo "  make format      - Format code"
	@echo "  make lint        - Run linters"
	@echo "  make type-check  - Run type checking"
	@echo "  make check       - Run all checks (format + lint + type check + tests)"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean       - Remove cache files and generated files"
	@echo ""


check-uv:
	@if ! command -v uv > /dev/null; then \
		echo "❌ uv not found. Install it with: curl -LsSf https://astral.sh/uv/install.sh | sh"; \
		exit 1; \
	fi
# Install dependencies (production only)
install: check-uv
	@echo "Installing dependencies with uv..."
	uv pip install -e .
	@echo "✅ Dependencies installed"

# Install all dependencies including dev tools
install-dev:
	@echo "Installing all dependencies (including dev tools) with uv..."
	uv pip install -e ".[dev]"
	@echo "✅ All dependencies (including dev tools) installed"

# Check if dependencies are installed
deps:
	@echo "Checking dependencies..."
	@python3 -c "import slack_bolt; print('✅ slack-bolt')" || echo "❌ slack-bolt not installed"
	@python3 -c "import dotenv; print('✅ python-dotenv')" || echo "❌ python-dotenv not installed"
	@python3 -c "import anthropic; print('✅ anthropic')" || echo "❌ anthropic not installed"
	@python3 -c "import sentence_transformers; print('✅ sentence-transformers')" || echo "❌ sentence-transformers not installed"
	@python3 -c "import chromadb; print('✅ chromadb')" || echo "❌ chromadb not installed"

# Run the bot
run:
	@echo "Starting Slack Repo Agent..."
	@if [ ! -f .env ]; then \
		echo "⚠️  Warning: .env file not found. Create one with SLACK_BOT_TOKEN and SLACK_APP_TOKEN"; \
	fi
	python3 -m benedict.main

# Run tests
test: check-uv
	@echo "Running tests..."
	pytest

# Run tests with coverage
test-cov: check-uv
	@echo "Running tests with coverage..."
	pytest --cov=src/benedict --cov-report=term-missing --cov-report=html

# Run unit tests only
test-unit: check-uv
	@echo "Running unit tests..."
	pytest tests/unit/

# Run integration tests only
test-integration: check-uv
	@echo "Running integration tests..."
	pytest tests/integration/

# Run tests in verbose mode
test-verbose: check-uv
	@echo "Running tests (verbose)..."
	pytest -vv

# Run tests and open coverage report
test-coverage-html: test-cov
	@echo "Opening coverage report..."
	@if command -v open > /dev/null; then \
		open htmlcov/index.html; \
	elif command -v xdg-open > /dev/null; then \
		xdg-open htmlcov/index.html; \
	else \
		echo "Coverage report generated at htmlcov/index.html"; \
	fi

# Linting
lint: check-uv
	@echo "Running linters..."
	@command -v ruff > /dev/null 2>&1 && ruff check src tests || echo "⚠️  ruff not installed"
	@command -v pylint > /dev/null 2>&1 && pylint src/benedict || echo "⚠️  pylint not installed"

# Type checking
type-check: check-uv
	@echo "Running type checker..."
	@command -v mypy > /dev/null 2>&1 && mypy src/benedict || echo "⚠️  mypy not installed"

# Code formatting
format: check-uv
	@echo "Formatting code..."
	@command -v black > /dev/null 2>&1 && black src tests || echo "⚠️  black not installed"
	@command -v ruff > /dev/null 2>&1 && ruff check --fix src tests || echo "⚠️  ruff not installed"
	@echo "✅ Code formatted"

# Format check (don't modify files)
format-check: check-uv
	@echo "Checking code format..."
	@command -v black > /dev/null 2>&1 && black --check src tests || echo "⚠️  black not installed"

# Run all checks
check: format-check lint type-check test-cov
	@echo "✅ All checks passed!"
clean:
	@echo "Cleaning up..."
	find . -type d -name "__pycache__" -exec rm -r {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -r {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -r {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -r {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -r {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -r {} + 2>/dev/null || true
	find . -type f -name ".coverage" -exec rm {} + 2>/dev/null || true
	find . -type f -name "coverage.xml" -exec rm {} + 2>/dev/null || true
	@echo "✅ Cleanup complete"
setup: venv
	@echo "Setting up development environment..."

# Sync dependencies (uv's recommended way - same as install but clearer intent)
sync:
	@echo "Syncing dependencies with uv..."
	@if ! command -v uv > /dev/null; then \
		echo "❌ uv not found. Install it with: curl -LsSf https://astral.sh/uv/install.sh | sh"; \
		exit 1; \
	fi
	uv pip install -e .
	@echo "✅ Dependencies synced"


# Sync all dependencies including dev tools
sync-dev: check-uv
	@echo "Syncing all dependencies (including dev tools) with uv..."
	uv pip install -e ".[dev]"
	@echo "✅ All dependencies (including dev tools) synced"

# Recreate virtual environment (nuke and rebuild)
recreate-env: check-uv
	@echo "Recreating virtual environment..."
	uv venv
	@echo "✅ Virtual environment recreated"
	@echo "Activate with: source .venv/bin/activate"
