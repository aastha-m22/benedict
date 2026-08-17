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
	@echo "  make test        - Run tests (if available)"
	@echo "  make format      - Format code"
	@echo "  make check       - Run all checks (format check + tests)"
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

test:
	@echo "Running tests..."
	python3 -m pytest tests/

ruff:
	@echo "Formatting code..."
	ruff check src 2>/dev/null || ruff check src
	@echo "✅ Code formatted"

black:
	@echo "Formatting code..."
	black src tests 2>/dev/null || black src
	@echo "✅ Code formatted"


format: black ruff
check: format test
clean:
	@echo "Cleaning up..."
	find . -type d -name "__pycache__" -exec rm -r {} + 2>/dev/null || true
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
