COMPOSE := docker compose
PROD_ENV ?= .env.production
PROD_COMPOSE := $(COMPOSE) --env-file $(PROD_ENV) -f docker-compose.production.yml
PROD_WAIT_TIMEOUT ?= 180
BACKEND_TEST_RUN := $(COMPOSE) run --rm -e DATE_PLANNER_PROJECT_ROOT=/workspace -v "$(CURDIR):/workspace:ro" backend
BACKEND_COVERAGE := pytest --cov=apps.common --cov-config=pyproject.toml --cov-report=term-missing:skip-covered --cov-report=xml:coverage.xml --cov-report=html:htmlcov

.PHONY: up down build logs migrate test test-backend test-frontend coverage coverage-backend coverage-frontend lint lint-backend lint-frontend format typecheck check check-backend check-migrations check-schema check-deploy check-prod-config build-frontend quality prod-build prod-preflight prod-up prod-down prod-logs prod-ps prod-release prod-backup prod-verify-restore prod-smoke

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
	$(BACKEND_TEST_RUN) pytest

test-frontend:
	$(COMPOSE) run --rm --no-deps frontend npm run test

coverage: coverage-backend coverage-frontend

coverage-backend:
	$(BACKEND_TEST_RUN) $(BACKEND_COVERAGE)

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

check: check-backend check-migrations check-schema check-deploy check-prod-config build-frontend

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

check-prod-config:
	$(COMPOSE) --env-file .env.production.example -f docker-compose.production.yml config --quiet
	$(COMPOSE) --env-file .env.production.example -f docker-compose.production.yml run --rm --no-deps proxy caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
	$(COMPOSE) run --rm --no-deps \
		-e DJANGO_SECRET_KEY=production-preflight-check-secret-with-more-than-fifty-unique-looking-characters \
		-e POSTGRES_PASSWORD=production-preflight-app-password-29-characters \
		-e POSTGRES_ADMIN_PASSWORD=production-preflight-admin-password-31-characters \
		-e POSTGRES_APP_PASSWORD=production-preflight-runtime-password-33-characters \
		-e POSTGRES_DB=date_planner \
		-e POSTGRES_ADMIN_USER=date_planner_admin \
		-e POSTGRES_APP_USER=date_planner_app \
		-e APP_DOMAIN=dates.company.dev \
		-e API_DOMAIN=api.dates.company.dev \
		-e ACME_EMAIL=operations@company.dev \
		-e DJANGO_SECURE_HSTS_SECONDS=3600 \
		-e DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS=False \
		-e DJANGO_SECURE_HSTS_PRELOAD=False \
		-e CADDY_HSTS=max-age=3600 \
		backend python -m config.production_environment

prod-build:
	test -f $(PROD_ENV) || (echo "Missing $(PROD_ENV). Copy .env.production.example and replace every placeholder." && exit 1)
	$(PROD_COMPOSE) build

prod-preflight:
	test -f $(PROD_ENV) || (echo "Missing $(PROD_ENV). Copy .env.production.example and replace every placeholder." && exit 1)
	$(PROD_COMPOSE) build preflight
	$(PROD_COMPOSE) run --rm --no-deps preflight

prod-up: prod-preflight
	$(PROD_COMPOSE) up --build --wait --wait-timeout $(PROD_WAIT_TIMEOUT)

prod-down:
	$(PROD_COMPOSE) down --remove-orphans

prod-logs:
	$(PROD_COMPOSE) logs --follow

prod-ps:
	$(PROD_COMPOSE) ps

prod-release: prod-preflight
	$(PROD_COMPOSE) run --rm release

prod-backup:
	test -n "$(BACKUP_DIR)" || (echo "Set BACKUP_DIR to an existing absolute directory." && exit 1)
	DATE_PLANNER_PROD_ENV_FILE="$(abspath $(PROD_ENV))" ./deploy/scripts/backup-postgres.sh "$(BACKUP_DIR)"

prod-verify-restore:
	test -n "$(BACKUP_FILE)" || (echo "Set BACKUP_FILE to an absolute .dump path." && exit 1)
	DATE_PLANNER_PROD_ENV_FILE="$(abspath $(PROD_ENV))" ./deploy/scripts/verify-postgres-restore.sh "$(BACKUP_FILE)"

prod-smoke:
	test -n "$(APP_ORIGIN)" || (echo "Set APP_ORIGIN to the public HTTPS app origin." && exit 1)
	test -n "$(API_ORIGIN)" || (echo "Set API_ORIGIN to the public HTTPS API origin." && exit 1)
	test -f $(PROD_ENV) || (echo "Missing $(PROD_ENV). Copy .env.production.example and replace every placeholder." && exit 1)
	$(PROD_COMPOSE) --profile operations build smoke
	$(PROD_COMPOSE) --profile operations run --rm --no-deps smoke --app-origin "$(APP_ORIGIN)" --api-origin "$(API_ORIGIN)" --allow-write

build-frontend:
	$(COMPOSE) run --rm --no-deps frontend npm run build

quality: lint check coverage
