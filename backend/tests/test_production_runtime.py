"""Regression tests for the production container runtime."""

import os
from pathlib import Path

from config.production_environment import collect_production_environment_errors

PROJECT_ROOT = Path(os.getenv("DATE_PLANNER_PROJECT_ROOT", Path(__file__).resolve().parents[2]))


def read_project_file(relative_path: str) -> str:
    return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")


def parse_example_environment() -> dict[str, str]:
    values: dict[str, str] = {}
    for line in read_project_file(".env.production.example").splitlines():
        if line and not line.startswith("#"):
            name, value = line.split("=", maxsplit=1)
            values[name] = value
    return values


def test_unchanged_production_environment_example_is_fail_closed() -> None:
    errors = collect_production_environment_errors(parse_example_environment())

    assert errors
    assert any("DJANGO_SECRET_KEY" in error for error in errors)
    assert any("POSTGRES_ADMIN_PASSWORD" in error for error in errors)
    assert any("POSTGRES_APP_PASSWORD" in error for error in errors)
    assert any("APP_DOMAIN" in error for error in errors)
    assert any("API_DOMAIN" in error for error in errors)
    assert any("ACME_EMAIL" in error for error in errors)


def test_production_compose_exposes_only_the_edge_proxy() -> None:
    compose = read_project_file("docker-compose.production.yml")

    assert compose.startswith("name: date-planner-production\n")
    assert compose.count("    ports:\n") == 1
    assert '      - "80:80"' in compose
    assert '      - "443:443"' in compose
    assert '      - "443:443/udp"' in compose
    assert "./backend:/app" not in compose
    assert "./frontend:/app" not in compose
    assert "  app:\n    internal: true" in compose
    assert "  data:\n    internal: true" in compose


def test_production_compose_has_release_health_and_persistence_contracts() -> None:
    compose = read_project_file("docker-compose.production.yml")

    assert "condition: service_completed_successfully" in compose
    assert compose.count("    healthcheck:\n") >= 4
    assert compose.count("    restart: unless-stopped\n") >= 4
    assert "postgres_data:/var/lib/postgresql" in compose
    assert "backend_static:/var/lib/date-planner/static" in compose
    assert "backend_static:/var/lib/date-planner/static:ro" in compose
    assert "caddy_data:/data" in compose
    assert "caddy_config:/config" in compose
    assert compose.count("dockerfile: Dockerfile.production") == 4
    assert "/api/v1/ready/" in compose
    assert "stop_grace_period: 40s" in compose
    assert "driver: local" in compose
    assert "log_min_error_statement=panic" in compose


def test_production_database_uses_a_non_superuser_application_role() -> None:
    compose = read_project_file("docker-compose.production.yml")
    init_script = read_project_file("deploy/postgres/init-app-role.sh")

    assert "POSTGRES_ADMIN_USER" in compose
    assert "POSTGRES_APP_USER" in compose
    assert "POSTGRES_USER: ${POSTGRES_APP_USER" in compose
    assert "NOSUPERUSER" in init_script
    assert "NOCREATEDB" in init_script
    assert "NOCREATEROLE" in init_script
    assert 'ALTER DATABASE :"database_name" OWNER TO :"app_user"' in init_script


def test_production_images_use_non_development_entrypoints() -> None:
    backend_dockerfile = read_project_file("backend/Dockerfile.production")
    frontend_dockerfile = read_project_file("frontend/Dockerfile.production")
    smoke_dockerfile = read_project_file("deploy/smoke/Dockerfile")
    release_script = read_project_file("backend/scripts/release-production.sh")

    assert "pip install ." in backend_dockerfile
    assert 'pip install ".[dev]"' not in backend_dockerfile
    assert "USER app" in backend_dockerfile
    assert "USER node" in frontend_dockerfile
    assert 'CMD ["node", ".output/server/index.mjs"]' in frontend_dockerfile
    assert "USER smoke" in smoke_dockerfile
    assert 'ENTRYPOINT ["python", "/usr/local/bin/date-planner-smoke"]' in smoke_dockerfile
    assert "manage.py check --deploy" in release_script
    assert "--fail-level WARNING" not in release_script
    assert "manage.py verify_database_role" in release_script
    assert "manage.py migrate --noinput" in release_script
    assert "manage.py collectstatic --noinput --clear" in release_script


def test_gunicorn_access_logs_cannot_capture_request_identifiers() -> None:
    start_script = read_project_file("backend/scripts/start-production.sh")

    assert "--access-logfile -" in start_script
    assert "--access-logformat" in start_script
    assert "--forwarded-allow-ips '*'" in start_script
    assert "--no-control-socket" in start_script
    for unsafe_atom in ("%(h)s", "%(r)s", "%(U)s", "%(q)s", "%(f)s", "%(a)s"):
        assert unsafe_atom not in start_script


def test_caddy_routes_domains_without_exposing_management_secrets() -> None:
    caddyfile = read_project_file("deploy/caddy/Caddyfile")

    assert "{$APP_DOMAIN}" in caddyfile
    assert "{$API_DOMAIN}" in caddyfile
    assert "reverse_proxy frontend:3000" in caddyfile
    assert "reverse_proxy backend:8000" in caddyfile
    assert "handle_path /static/*" in caddyfile
    assert "root * /srv/backend-static" in caddyfile
    assert "token=" not in caddyfile
    assert "/manage/" not in caddyfile
    assert "-X-Powered-By" in caddyfile
    assert caddyfile.count("\n\tlog ") == 1
    assert "\n\tlog default {" in caddyfile
    assert "request delete" in caddyfile
    assert "exclude http.log.access" in caddyfile


def test_django_collects_static_files_to_an_explicit_root() -> None:
    settings = read_project_file("backend/config/settings.py")

    assert 'STATIC_URL = "/static/"' in settings
    assert "DJANGO_STATIC_ROOT" in settings
    assert 'BASE_DIR / "staticfiles"' in settings


def test_ci_validates_and_builds_the_production_runtime() -> None:
    workflow = read_project_file(".github/workflows/ci.yml")

    assert "Production runtime checks" in workflow
    assert "config --quiet" in workflow
    assert "caddy validate" in workflow
    assert "build backend frontend" in workflow
    assert "Reject unsafe production environment values" in workflow


def test_backup_and_restore_scripts_verify_real_recovery() -> None:
    backup_script = read_project_file("deploy/scripts/backup-postgres.sh")
    restore_script = read_project_file("deploy/scripts/verify-postgres-restore.sh")
    runbook = read_project_file("docs/production-runbook.md")

    assert "pg_dump" in backup_script
    assert "--format=custom" in backup_script
    assert "sha256sum" in backup_script
    assert "pg_restore --list" in backup_script
    assert "--single-transaction" in restore_script
    assert "manage.py migrate --check" in restore_script
    assert "dropdb" in restore_script
    assert "--force" in restore_script
    assert "RPO" in runbook
    assert "RTO" in runbook
    assert "off the Docker host" in runbook
