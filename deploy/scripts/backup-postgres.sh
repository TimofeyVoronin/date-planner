#!/bin/sh

set -eu
umask 077

usage() {
    cat <<'EOF'
Usage: deploy/scripts/backup-postgres.sh ABSOLUTE_BACKUP_DIRECTORY

Create a PostgreSQL custom-format backup and a matching SHA-256 checksum.

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

backup_directory=$1
case "$backup_directory" in
    /*) ;;
    *)
        echo "Backup directory must be an absolute path." >&2
        exit 2
        ;;
esac

if [ ! -d "$backup_directory" ]; then
    echo "Backup directory does not exist: $backup_directory" >&2
    exit 2
fi
if [ ! -w "$backup_directory" ]; then
    echo "Backup directory is not writable: $backup_directory" >&2
    exit 2
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

timestamp=$(date -u "+%Y%m%dT%H%M%SZ")
backup_name="date-planner-postgres-$timestamp.dump"
backup_file="$backup_directory/$backup_name"
checksum_file="$backup_file.sha256"

if [ -e "$backup_file" ] || [ -e "$checksum_file" ]; then
    echo "Refusing to overwrite an existing backup: $backup_file" >&2
    exit 1
fi

temporary_backup=
temporary_checksum=
backup_published=false
checksum_published=false
completed=false

cleanup() {
    result=$?
    trap - EXIT HUP INT TERM
    if [ -n "$temporary_backup" ]; then
        rm -f -- "$temporary_backup"
    fi
    if [ -n "$temporary_checksum" ]; then
        rm -f -- "$temporary_checksum"
    fi
    if [ "$completed" = false ]; then
        if [ "$backup_published" = true ]; then
            rm -f -- "$backup_file"
        fi
        if [ "$checksum_published" = true ]; then
            rm -f -- "$checksum_file"
        fi
    fi
    exit "$result"
}
trap cleanup EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM

temporary_backup=$(mktemp "$backup_directory/.date-planner-postgres.XXXXXX.dump")
temporary_checksum=$(mktemp "$backup_directory/.date-planner-postgres.XXXXXX.sha256")
chmod 600 "$temporary_backup" "$temporary_checksum"

echo "Creating a consistent PostgreSQL custom-format backup..." >&2
compose exec -T db sh -eu -c \
    'app_user=${POSTGRES_APP_USER:-$POSTGRES_USER}; exec pg_dump --username="$app_user" --dbname="$POSTGRES_DB" --format=custom --no-owner --no-privileges' \
    >"$temporary_backup"

if [ ! -s "$temporary_backup" ]; then
    echo "The backup is empty; no output file was published." >&2
    exit 1
fi

compose exec -T db pg_restore --list <"$temporary_backup" >/dev/null

digest=$(sha256sum "$temporary_backup" | awk '{print $1}')
printf '%s  %s\n' "$digest" "$backup_name" >"$temporary_checksum"

ln "$temporary_backup" "$backup_file"
backup_published=true
ln "$temporary_checksum" "$checksum_file"
checksum_published=true
rm -f -- "$temporary_backup" "$temporary_checksum"
temporary_backup=
temporary_checksum=
completed=true

echo "Backup created and archive structure verified:" >&2
printf '%s\n' "$backup_file"
