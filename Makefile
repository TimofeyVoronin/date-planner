COMPOSE := docker compose
BACKEND_COVERAGE := pytest --cov=apps.common --cov-config=pyproject.toml --cov-report=term-missing:skip-covered --cov-report=xml:coverage.xml --cov-report=html:htmlcov

.PHONY: up down build logs migrate test test-backend test-frontend coverage coverage-backend coverage-frontend lint lint-backend lint-frontend format typecheck check check-backend check-migrations check-schema build-frontend quality

up:
	$(COMPOSE) up --build

down:
	$(COMPOSE) down --remove-orphans

build:
	$(COMPOSE) build

logs:
	$(COMPOSE) logs --follow

migrate:
	$(COMPOSE) run --rm backend python manage.py migrate

test: test-backend test-frontend

test-backend:
	$(COMPOSE) run --rm backend pytest

test-frontend:
	$(COMPOSE) run --rm --no-deps frontend npm run test

coverage: coverage-backend coverage-frontend

coverage-backend:
	$(COMPOSE) run --rm backend $(BACKEND_COVERAGE)

coverage-frontend:
	$(COMPOSE) run --rm --no-deps frontend npm run test:coverage

lint: lint-backend lint-frontend typecheck

lint-backend:
	$(COMPOSE) run --rm --no-deps backend ruff check .
	$(COMPOSE) run --rm --no-deps backend ruff format --check .

lint-frontend:
	$(COMPOSE) run --rm --no-deps frontend npm run lint

format:
	$(COMPOSE) run --rm --no-deps backend ruff format .
	$(COMPOSE) run --rm --no-deps backend ruff check --fix .
	$(COMPOSE) run --rm --no-deps frontend npm run lint -- --fix

typecheck:
	$(COMPOSE) run --rm --no-deps frontend npm run typecheck

check: check-backend check-migrations check-schema build-frontend

check-backend:
	$(COMPOSE) run --rm backend python manage.py check

check-migrations:
	$(COMPOSE) run --rm backend python manage.py makemigrations --check --dry-run

check-schema:
	$(COMPOSE) run --rm backend python manage.py spectacular --file /tmp/date-planner-schema.yaml --validate

build-frontend:
	$(COMPOSE) run --rm --no-deps frontend npm run build

quality: lint check coverage
