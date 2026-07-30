#!/bin/sh

set -eu

usage() {
    cat <<'EOF'
Usage: deploy/scripts/verify-postgres-restore.sh ABSOLUTE_BACKUP_FILE

Verify the checksum and restore a PostgreSQL custom-format backup into a new,
isolated temporary database. The production database is never used as a restore
target. The temporary database is removed on exit.

Optional environment variables:
  DATE_PLANNER_PROD_COMPOSE_FILE  Compose file (default: docker-compose.production.yml)
  DATE_PLANNER_PROD_ENV_FILE      Compose env file (default: .env.production)
EOF
}

case "${1:-}" in
    -h|--help)
        usage
        exit 0
        ;;
esac

if [ "$#" -ne 1 ]; then
    usage >&2
    exit 2
fi

backup_file=$1
case "$backup_file" in
    /*) ;;
    *)
        echo "Backup file must be an absolute path." >&2
        exit 2
        ;;
esac

checksum_file="$backup_file.sha256"
if [ ! -f "$backup_file" ] || [ ! -r "$backup_file" ]; then
    echo "Backup file is not readable: $backup_file" >&2
    exit 2
fi
if [ ! -f "$checksum_file" ] || [ ! -r "$checksum_file" ]; then
    echo "Checksum file is not readable: $checksum_file" >&2
    exit 2
fi

expected_digest=$(awk 'NR == 1 { print $1 }' "$checksum_file")
case "$expected_digest" in
    *[!0-9A-Fa-f]*|"")
        echo "Checksum file does not contain a valid SHA-256 digest." >&2
        exit 1
        ;;
esac
if [ "${#expected_digest}" -ne 64 ]; then
    echo "Checksum file does not contain a valid SHA-256 digest." >&2
    exit 1
fi
expected_digest=$(printf '%s' "$expected_digest" | tr "A-F" "a-f")

actual_digest=$(sha256sum "$backup_file" | awk '{print $1}')
if [ "$actual_digest" != "$expected_digest" ]; then
    echo "Backup checksum verification failed." >&2
    exit 1
fi

script_directory=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
project_root=$(CDPATH= cd -- "$script_directory/../.." && pwd -P)
compose_file=${DATE_PLANNER_PROD_COMPOSE_FILE:-"$project_root/docker-compose.production.yml"}
env_file=${DATE_PLANNER_PROD_ENV_FILE:-"$project_root/.env.production"}

if [ ! -f "$compose_file" ]; then
    echo "Compose file does not exist: $compose_file" >&2
    exit 2
fi
if [ ! -f "$env_file" ]; then
    echo "Production env file does not exist: $env_file" >&2
    exit 2
fi

compose() {
    docker compose --env-file "$env_file" -f "$compose_file" "$@"
}

compose exec -T db pg_restore --list <"$backup_file" >/dev/null

timestamp=$(date -u "+%Y%m%d%H%M%S")
verify_database="date_planner_restore_verify_${timestamp}_$$"
database_created=false

cleanup() {
    result=$?
    trap - EXIT HUP INT TERM
    if [ "$database_created" = true ]; then
        if ! compose exec -T -e VERIFY_DATABASE="$verify_database" db sh -eu -c \
            'exec dropdb --username="$POSTGRES_USER" --if-exists --force "$VERIFY_DATABASE"'
        then
            echo "WARNING: could not remove temporary database: $verify_database" >&2
            if [ "$result" -eq 0 ]; then
                result=1
            fi
        fi
    fi
    exit "$result"
}
trap cleanup EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM

production_database=$(
    compose exec -T db sh -eu -c 'printf "%s" "$POSTGRES_DB"'
)
if [ "$verify_database" = "$production_database" ]; then
    echo "Refusing to use the production database as a restore target." >&2
    exit 1
fi

echo "Creating isolated restore database: $verify_database" >&2
compose exec -T -e VERIFY_DATABASE="$verify_database" db sh -eu -c \
    'app_user=${POSTGRES_APP_USER:-$POSTGRES_USER}; exec createdb --username="$POSTGRES_USER" --owner="$app_user" --template=template0 "$VERIFY_DATABASE"'
database_created=true

compose exec -T -e VERIFY_DATABASE="$verify_database" db sh -eu -c \
    'app_user=${POSTGRES_APP_USER:-$POSTGRES_USER}; exec pg_restore --username="$app_user" --dbname="$VERIFY_DATABASE" --exit-on-error --single-transaction --no-owner --no-privileges' \
    <"$backup_file"

compose run --rm --no-deps -T \
    -e POSTGRES_DB="$verify_database" \
    backend python manage.py migrate --check

compose exec -T -e VERIFY_DATABASE="$verify_database" db sh -eu -c \
    'app_user=${POSTGRES_APP_USER:-$POSTGRES_USER}; exec psql --username="$app_user" --dbname="$VERIFY_DATABASE" --no-psqlrc --set=ON_ERROR_STOP=1' \
    <<'SQL'
DO $restore_verification$
DECLARE
    invalid_rows bigint;
BEGIN
    IF to_regclass('public.django_migrations') IS NULL THEN
        RAISE EXCEPTION 'required table django_migrations is missing';
    END IF;
    IF to_regclass('public.common_invitation') IS NULL THEN
        RAISE EXCEPTION 'required table common_invitation is missing';
    END IF;
    IF to_regclass('public.common_confirmedplan') IS NULL THEN
        RAISE EXCEPTION 'required table common_confirmedplan is missing';
    END IF;

    SELECT count(*)
      INTO invalid_rows
      FROM common_invitation
     WHERE (publication_status = 'draft' AND published_at IS NOT NULL)
        OR (publication_status = 'published' AND published_at IS NULL)
        OR (response_status = 'pending' AND responded_at IS NOT NULL)
        OR (response_status IN ('accepted', 'declined') AND responded_at IS NULL)
        OR (creation_mode = 'quick' AND planning_mode <> 'after_acceptance');
    IF invalid_rows <> 0 THEN
        RAISE EXCEPTION 'invitation lifecycle invariant failed for % row(s)', invalid_rows;
    END IF;

    SELECT count(*)
      INTO invalid_rows
      FROM common_confirmedplan
     WHERE confirmed_at >= starts_at;
    IF invalid_rows <> 0 THEN
        RAISE EXCEPTION 'confirmed plan time invariant failed for % row(s)', invalid_rows;
    END IF;

    SELECT count(*)
      INTO invalid_rows
      FROM pg_constraint
     WHERE connamespace = 'public'::regnamespace
       AND NOT convalidated;
    IF invalid_rows <> 0 THEN
        RAISE EXCEPTION 'restore contains % unvalidated constraint(s)', invalid_rows;
    END IF;
END
$restore_verification$;
SQL

echo "Restore verification passed; the temporary database will now be removed." >&2
