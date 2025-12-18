# Makefile for GitLab Hierarchy Extractor
# Provides convenient shortcuts for common development tasks

.PHONY: help install install-dev test test-cov lint format type-check clean docs run-example

# Default target - show help
help:
	@echo "GitLab Hierarchy Extractor - Development Commands"
	@echo ""
	@echo "Setup:"
	@echo "  make install        Install package in production mode"
	@echo "  make install-dev    Install package with development dependencies"
	@echo "  make setup          Complete development setup (venv + install + hooks)"
	@echo ""
	@echo "Testing:"
	@echo "  make test           Run all tests"
	@echo "  make test-cov       Run tests with coverage report"
	@echo "  make test-unit      Run only unit tests"
	@echo "  make test-int       Run only integration tests"
	@echo "  make test-watch     Run tests in watch mode"
	@echo ""
	@echo "Code Quality:"
	@echo "  make lint           Run linter (flake8)"
	@echo "  make format         Format code (black)"
	@echo "  make format-check   Check formatting without changes"
	@echo "  make type-check     Run type checker (mypy)"
	@echo "  make quality        Run all quality checks (lint + format + type)"
	@echo ""
	@echo "Documentation:"
	@echo "  make docs           Generate documentation"
	@echo "  make docs-serve     Serve documentation locally"
	@echo ""
	@echo "Examples:"
	@echo "  make run-example    Run extraction example"
	@echo "  make run-query      Run query example"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean          Remove build artifacts and cache files"
	@echo "  make clean-db       Remove example databases"
	@echo "  make clean-all      Remove everything (clean + venv)"
	@echo ""
	@echo "Distribution:"
	@echo "  make build          Build distribution packages"
	@echo "  make publish        Publish to PyPI (requires credentials)"
	@echo "  make publish-test   Publish to Test PyPI"

# Installation targets
install:
	pip install .

install-dev:
	pip install -e ".[dev]"

setup: clean
	python -m venv venv
	./venv/bin/pip install --upgrade pip
	./venv/bin/pip install -e ".[dev]"
	./venv/bin/pre-commit install
	@echo ""
	@echo "Setup complete! Activate virtualenv with:"
	@echo "  source venv/bin/activate  (Linux/Mac)"
	@echo "  venv\\Scripts\\activate     (Windows)"

# Testing targets
test:
	pytest

test-cov:
	pytest --cov=gitlab_hierarchy --cov-report=term-missing --cov-report=html
	@echo ""
	@echo "Coverage report generated in htmlcov/index.html"

test-unit:
	pytest -m unit

test-int:
	pytest -m integration

test-watch:
	pytest-watch

# Code quality targets
lint:
	flake8 gitlab_hierarchy tests examples

format:
	black gitlab_hierarchy tests examples

format-check:
	black --check gitlab_hierarchy tests examples

type-check:
	mypy gitlab_hierarchy

quality: format-check lint type-check
	@echo "All quality checks passed!"

# Documentation targets
docs:
	@echo "Generating documentation..."
	@echo "README.md, ARCHITECTURE.md, and CONTRIBUTING.md are already present"
	@echo "API documentation can be generated with sphinx if needed"

docs-serve:
	@echo "Serving documentation..."
	@echo "Open docs/ARCHITECTURE.md in your browser"

# Example targets
run-example:
	@echo "Running extraction example..."
	@if [ -z "$$GITLAB_TOKEN" ]; then \
		echo "Error: GITLAB_TOKEN environment variable not set"; \
		echo "Set it with: export GITLAB_TOKEN='your-token'"; \
		exit 1; \
	fi
	python examples/extract_hierarchy.py

run-query:
	@echo "Running query example..."
	@if [ ! -f hierarchy.db ]; then \
		echo "Error: hierarchy.db not found"; \
		echo "Run 'make run-example' first to create database"; \
		exit 1; \
	fi
	python examples/query_hierarchy.py

# Cleanup targets
clean:
	@echo "Cleaning build artifacts..."
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf .coverage
	rm -rf htmlcov/
	rm -rf .eggs/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name '*.pyc' -delete
	find . -type f -name '*.pyo' -delete
	find . -type f -name '*~' -delete
	@echo "Clean complete!"

clean-db:
	@echo "Removing example databases..."
	rm -f hierarchy.db
	rm -f *.db

clean-all: clean clean-db
	@echo "Removing virtual environment..."
	rm -rf venv/
	@echo "All clean!"

# Distribution targets
build: clean
	python -m build

publish: build
	python -m twine upload dist/*

publish-test: build
	python -m twine upload --repository testpypi dist/*

# Development workflow targets
dev-setup: setup
	@echo "Development environment ready!"

dev-check: quality test
	@echo "All checks passed! Ready to commit."

pre-commit: format lint type-check test
	@echo "Pre-commit checks complete!"

# CI simulation
ci: quality test-cov
	@echo "CI simulation complete!"

# Quick development cycle
quick: format test
	@echo "Quick check complete!"

# Database management
db-stats:
	@if [ ! -f hierarchy.db ]; then \
		echo "Error: hierarchy.db not found"; \
		exit 1; \
	fi
	neo stats --db hierarchy.db

db-cleanup:
	@if [ ! -f hierarchy.db ]; then \
		echo "Error: hierarchy.db not found"; \
		exit 1; \
	fi
	neo cleanup --db hierarchy.db --keep-days 30

db-export:
	@if [ ! -f hierarchy.db ]; then \
		echo "Error: hierarchy.db not found"; \
		exit 1; \
	fi
	neo export --db hierarchy.db --format csv --output hierarchy.csv
	@echo "Exported to hierarchy.csv"

# Version management
version:
	@python -c "import gitlab_hierarchy; print(f'Version: {gitlab_hierarchy.__version__}')"

# Requirements management
requirements:
	pip freeze > requirements-freeze.txt
	@echo "Requirements frozen to requirements-freeze.txt"

# Git helpers
git-status:
	@git status --short

git-clean:
	git clean -fdx -e venv -e .env

# Docker targets (if Docker support is added)
docker-build:
	docker build -t neo-extractor .

docker-run:
	docker run --rm -it \
		-e GITLAB_TOKEN=$${GITLAB_TOKEN} \
		-e GITLAB_URL=$${GITLAB_URL} \
		-v $$(pwd)/data:/data \
		neo-extractor

# Help for common issues
troubleshoot:
	@echo "Common Issues and Solutions:"
	@echo ""
	@echo "1. Tests failing:"
	@echo "   - Run: make clean && make install-dev && make test"
	@echo ""
	@echo "2. Import errors:"
	@echo "   - Activate venv: source venv/bin/activate"
	@echo "   - Reinstall: make install-dev"
	@echo ""
	@echo "3. GitLab API errors:"
	@echo "   - Check GITLAB_TOKEN is set"
	@echo "   - Verify token has api scope"
	@echo "   - Check network connectivity"
	@echo ""
	@echo "4. Database errors:"
	@echo "   - Remove old database: rm hierarchy.db"
	@echo "   - Re-run extraction: make run-example"
	@echo ""
	@echo "5. Style/lint errors:"
	@echo "   - Auto-fix: make format"
	@echo "   - Check remaining: make lint"
