# Developer shortcuts. `make help` lists them.
#
# Local development needs Python >= 3.12 and a PostgreSQL 16 server; `make db` starts one in
# Docker (127.0.0.1:5432, user/password/database = portal) that matches config.settings.local.

PYTHON  ?= python3
VENV    ?= .venv
BIN     := $(VENV)/bin
MANAGE  := $(BIN)/python manage.py

.DEFAULT_GOAL := help
.PHONY: help venv install db run migrate seed reset-demo admin test test-fast lint format typecheck \
        check schema up down logs shell clean

help: ## Show this help
	@awk 'BEGIN {FS = ":.*##"} /^[a-zA-Z_-]+:.*##/ {printf "  \033[1m%-12s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

$(BIN)/python:
	$(PYTHON) -m venv $(VENV)
	$(BIN)/pip install --upgrade pip

venv: $(BIN)/python ## Create the virtual environment

install: venv ## Install runtime + development dependencies
	$(BIN)/pip install -r requirements-dev.txt

db: ## Start only PostgreSQL 16 in Docker (for running Django on the host)
	docker compose up -d --wait db

run: ## Run the dev server on http://localhost:8000 (config.settings.local)
	DJANGO_SETTINGS_MODULE=config.settings.local $(MANAGE) runserver

migrate: ## Apply database migrations (local settings)
	DJANGO_SETTINGS_MODULE=config.settings.local $(MANAGE) migrate_locked

seed: migrate ## Load the catalogue and the demo accounts/requests (password Demo@1234)
	DJANGO_SETTINGS_MODULE=config.settings.local $(MANAGE) sync_catalog
	DJANGO_SETTINGS_MODULE=config.settings.local $(MANAGE) seed_demo_data

reset-demo: ## Put the demo data back to its starting state (asks first)
	DJANGO_SETTINGS_MODULE=config.settings.local $(MANAGE) seed_demo_data --reset

admin: ## Create an administrator (prompts for the password; never stores it in shell history)
	@read -p "username: " u; read -p "name (Persian): " fa; read -p "name (English): " en; \
	DJANGO_SETTINGS_MODULE=config.settings.local $(MANAGE) bootstrap_admin \
		--username "$$u" --name-fa "$$fa" --name-en "$$en"

test: ## Run the whole test-suite (needs PostgreSQL; uses a throw-away test database)
	$(BIN)/python -m pytest

test-fast: ## Skip the slower multi-connection concurrency tests
	$(BIN)/python -m pytest -m "not concurrency"

lint: ## Ruff: lint + formatting check
	$(BIN)/ruff check .
	$(BIN)/ruff format --check .

format: ## Apply Ruff's formatting and safe fixes
	$(BIN)/ruff check --fix .
	$(BIN)/ruff format .

typecheck: ## mypy (strict) with django-stubs
	$(BIN)/mypy .

check: lint typecheck ## Everything CI runs: lint, types, migrations in sync, OpenAPI valid, tests
	DJANGO_SETTINGS_MODULE=config.settings.test $(MANAGE) makemigrations --check --dry-run
	DJANGO_SETTINGS_MODULE=config.settings.test $(MANAGE) spectacular --validate --fail-on-warn --file /dev/null
	$(BIN)/python -m pytest

schema: ## Write the OpenAPI 3 document to schema.yml
	DJANGO_SETTINGS_MODULE=config.settings.test $(MANAGE) spectacular --validate --fail-on-warn --file schema.yml

up: ## Build and start the demo stack (API on :8000, PostgreSQL 16)
	docker compose up --build -d --wait
	@echo "API: http://localhost:8000   docs: http://localhost:8000/api/docs/"

down: ## Stop the demo stack (keeps the database volume)
	docker compose down

logs: ## Follow the API logs
	docker compose logs -f web

shell: ## Django shell inside the running API container
	docker compose exec web python manage.py shell

clean: ## Remove caches and build leftovers (not the virtualenv or the database)
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
	rm -rf .pytest_cache .mypy_cache .ruff_cache schema.yml
