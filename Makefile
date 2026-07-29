COMPOSE := docker compose
BACKEND_COVERAGE := pytest --cov=apps.common --cov-config=pyproject.toml --cov-report=term-missing:skip-covered --cov-report=xml:coverage.xml --cov-report=html:htmlcov

.PHONY: up down build logs migrate test test-backend test-frontend coverage coverage-backend coverage-frontend lint lint-backend lint-frontend format typecheck check check-backend check-migrations check-schema check-deploy build-frontend quality

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

check: check-backend check-migrations check-schema check-deploy build-frontend

check-backend:
	$(COMPOSE) run --rm backend python manage.py check

check-migrations:
	$(COMPOSE) run --rm backend python manage.py makemigrations --check --dry-run

check-schema:
	$(COMPOSE) run --rm backend python manage.py spectacular --file /tmp/date-planner-schema.yaml --validate

check-deploy:
	$(COMPOSE) run --rm --no-deps \
		-e DJANGO_SECRET_KEY=deploy-check-only-secret-key-with-more-than-fifty-random-looking-characters \
		-e DJANGO_DEBUG=False \
		-e DJANGO_ALLOWED_HOSTS=api.example.com \
		-e CORS_ALLOWED_ORIGINS=https://example.com \
		-e CSRF_TRUSTED_ORIGINS=https://example.com \
		-e DJANGO_TRUST_PROXY_HEADERS=True \
		-e DJANGO_SECURE_SSL_REDIRECT=True \
		-e DJANGO_SESSION_COOKIE_SECURE=True \
		-e DJANGO_CSRF_COOKIE_SECURE=True \
		-e DJANGO_SECURE_HSTS_SECONDS=3600 \
		-e DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS=True \
		-e DJANGO_SECURE_HSTS_PRELOAD=True \
		-e DRF_NUM_PROXIES=1 \
		backend python manage.py check --deploy --fail-level WARNING

build-frontend:
	$(COMPOSE) run --rm --no-deps frontend npm run build

quality: lint check coverage
