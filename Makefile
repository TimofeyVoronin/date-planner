COMPOSE := docker compose

.PHONY: up down build logs migrate test test-backend test-frontend lint lint-backend lint-frontend format typecheck

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

lint: lint-backend lint-frontend typecheck

lint-backend:
	$(COMPOSE) run --rm --no-deps backend ruff check .

lint-frontend:
	$(COMPOSE) run --rm --no-deps frontend npm run lint

format:
	$(COMPOSE) run --rm --no-deps backend ruff format .
	$(COMPOSE) run --rm --no-deps backend ruff check --fix .
	$(COMPOSE) run --rm --no-deps frontend npm run lint -- --fix

typecheck:
	$(COMPOSE) run --rm --no-deps frontend npm run typecheck
