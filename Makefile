.PHONY: help install sync run test clean lint format check deps venv setup recreate-env

# Default target
help:
	@echo "Slack Repo Agent - Makefile Commands"
	@echo "======================================"
	@echo ""
	@echo "Setup:"
	@echo "  make install     - Install dependencies with uv"
	@echo "  make sync        - Sync dependencies with uv (recommended)"
	@echo "  make deps        - Check if dependencies are installed"
	@echo "  make recreate-env - Remove and recreate virtual environment with dependencies"
	@echo ""
	@echo "Running:"
	@echo "  make run         - Run the bot"
	@echo ""
	@echo "Development:"
	@echo "  make test        - Run tests (if available)"
	@echo "  make lint        - Run linters"
	@echo "  make format      - Format code"
	@echo "  make check       - Run all checks (lint + format check)"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean       - Remove cache files and generated files"
	@echo ""

# Install dependencies
install:
	@echo "Installing dependencies with uv..."
	@if ! command -v uv > /dev/null; then \
		echo "❌ uv not found. Install it with: curl -LsSf https://astral.sh/uv/install.sh | sh"; \
		exit 1; \
	fi
	uv pip install -e .
	@echo "✅ Dependencies installed"

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

# Run tests (placeholder - add tests later)
test:
	@echo "Running tests..."
	@echo "⚠️  No tests configured yet"
	@# python3 -m pytest tests/

# Lint code
lint:
	@echo "Running linters..."
	@if command -v pylint > /dev/null; then \
		pylint --disable=all --enable=E,F *.py || true; \
	else \
		echo "⚠️  pylint not installed. Install with: uv pip install pylint"; \
	fi
	@if command -v flake8 > /dev/null; then \
		flake8 *.py --max-line-length=100 --ignore=E501,W503 || true; \
	else \
		echo "⚠️  flake8 not installed. Install with: uv pip install flake8"; \
	fi

# Format code
format:
	@echo "Formatting code..."
	@if command -v black > /dev/null; then \
		black *.py; \
		echo "✅ Code formatted"; \
	else \
		echo "⚠️  black not installed. Install with: uv pip install black"; \
	fi

# Check code formatting
check:
	@echo "Checking code formatting..."
	@if command -v black > /dev/null; then \
		black --check *.py || echo "❌ Code needs formatting. Run: make format"; \
	else \
		echo "⚠️  black not installed. Install with: uv pip install black"; \
	fi

# Clean cache files and generated files
clean:
	@echo "Cleaning up..."
	find . -type d -name "__pycache__" -exec rm -r {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true
	find . -type f -name ".DS_Store" -delete 2>/dev/null || true
	@echo "✅ Cleanup complete"

# Create virtual environment with uv
venv:
	@echo "Creating virtual environment with uv..."
	@if ! command -v uv > /dev/null; then \
		echo "❌ uv not found. Install it with: curl -LsSf https://astral.sh/uv/install.sh | sh"; \
		exit 1; \
	fi
	uv venv
	@echo "✅ Virtual environment created"
	@echo "Activate with: source .venv/bin/activate"

# Setup development environment
setup: venv
	@echo "Setting up development environment..."
	@echo "Activate virtual environment: source .venv/bin/activate"
	@echo "Then run: make sync"

# Sync dependencies (uv's recommended way - same as install but clearer intent)
sync:
	@echo "Syncing dependencies with uv..."
	@if ! command -v uv > /dev/null; then \
		echo "❌ uv not found. Install it with: curl -LsSf https://astral.sh/uv/install.sh | sh"; \
		exit 1; \
	fi
	uv pip install -e .
	@echo "✅ Dependencies synced"

# Recreate virtual environment (nuke and rebuild)
recreate-env:
	@echo "Recreating virtual environment..."
	@if ! command -v uv > /dev/null; then \
		echo "❌ uv not found. Install it with: curl -LsSf https://astral.sh/uv/install.sh | sh"; \
		exit 1; \
	fi
	@if [ -d .venv ]; then \
		echo "Removing existing .venv directory..."; \
		rm -rf .venv; \
	fi
	@echo "Creating new virtual environment..."
	uv venv
	@echo "Installing dependencies..."
	uv pip install -e .
	@echo "✅ Virtual environment recreated and dependencies installed"
	@echo "Activate with: source .venv/bin/activate"
