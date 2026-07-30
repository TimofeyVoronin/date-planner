# Production runbook

## Post-deployment availability and privacy checks

After every release, run the full public-domain smoke from a network outside the
application containers:

```sh
make prod-smoke \
  APP_ORIGIN=https://example.com \
  API_ORIGIN=https://api.example.com
```

The command deliberately creates one synthetic confirmed invitation. Review the
home page, recipient page, builder/management page, date selection, activity
selection, waiting stage, and final card once in a real browser as well; the
automated smoke covers the same HTTP lifecycle and server-rendered metadata but
does not replace browser rendering and interaction checks.

The HTTP smoke does not execute the runaway decline button. For every release
that changes the recipient response flow, open a separate pending invitation in
a real browser and verify all of the following:

- with a mouse, the decline button moves on the first four approaches and the
  fifth click submits the decline;
- in touch-device emulation, the first four taps move the button and the fifth
  tap submits the decline;
- keyboard activation submits the decline immediately;
- with reduced motion enabled at the operating-system or browser level, the
  first pointer activation submits the decline without movement;
- if the fifth request fails, the invitation question remains visible and an
  explicit retry succeeds after connectivity is restored;
- after a successful save, reload restores the neutral declined stage and the
  explicit change-to-acceptance action still works before final confirmation.

Immediately inspect all service logs and confirm that the smoke names, request
paths, query strings, and capability markers are absent:

```sh
docker compose --env-file .env.production \
  -f docker-compose.production.yml logs --no-color |
  grep -E 'Production Smoke (Author|Recipient)|management_token|token='
```

Success is no output and `grep` exit status `1`. Do not paste logs into an issue
or chat. Caddy request access logs are disabled, Caddy error log request objects
are removed, Gunicorn records only method/status/size/duration, and Django uses a
fixed privacy-safe JSON schema. Keep those constraints when shipping logs to an
external collector.

Monitor both `https://example.com/` and
`https://api.example.com/api/v1/ready/` from outside the Docker host at least
once per minute. Alert after three consecutive failures and on TLS certificate
expiry, low disk space, unhealthy containers, failed release, stale backup,
failed restore drill, or sustained HTTP 5xx growth. Docker restart policies
restart terminated processes; they do not repair a process that stays alive but
is merely marked unhealthy, so an alert and an operator runbook are still
required.

## PostgreSQL role initialization

On an empty `postgres_data` volume, the official image creates the configured
admin role and then `deploy/postgres/init-app-role.sh` creates a separate
non-superuser application role. Django, Gunicorn, migrations, and logical dumps
use only that application role. The release step verifies the live PostgreSQL
flags and stops if Django can create databases, create roles, replicate, or act
as a superuser.

Initialization scripts do not run against an existing PostgreSQL volume. If a
volume was created by an older Compose configuration where Django used the
bootstrap superuser, do not start the new application stack directly. First
create and verify a backup, schedule a maintenance window, create a separate
admin role, demote the application role with `NOSUPERUSER NOCREATEDB NOCREATEROLE
NOREPLICATION`, and update both credentials in `.env.production`. Enter new
passwords interactively with `psql` rather than putting them in shell history.
Confirm the role flags and run `make prod-release` before reopening traffic.

## PostgreSQL backups and restore verification

The PostgreSQL named volume protects data from an ordinary container
replacement, but it is not a backup. A production backup must leave the Docker
host, be encrypted, and be verified by an actual restore.

The scripts below use PostgreSQL's custom archive format. `pg_dump` creates a
transactionally consistent logical dump without stopping normal reads or
writes. The corresponding restore drill uses `pg_restore` and never restores
over the production database. See the official PostgreSQL documentation for
[SQL dump backups](https://www.postgresql.org/docs/18/backup-dump.html) and
[`pg_restore`](https://www.postgresql.org/docs/18/app-pgrestore.html).

Prerequisites are Docker Compose, `sha256sum`, enough free space for the dump
and a restored copy of the database, a healthy `db` service, and a built
production backend image. The configured admin role creates and removes the
temporary verification database; the restricted application role owns restored
objects and runs the Django checks.

### Create a backup

Run the command on the production host from the repository root. The destination
directory must already exist, be writable, and be an absolute path:

```sh
deploy/scripts/backup-postgres.sh /srv/date-planner/backups
```

The command creates two mode-`0600` files:

- `date-planner-postgres-YYYYmmddTHHMMSSZ.dump`, a PostgreSQL custom archive;
- the matching `.dump.sha256` checksum.

The archive is first written to a temporary file in the destination directory.
It is published under its final name only after `pg_dump` succeeds, the file is
non-empty, and `pg_restore --list` can read it. Existing backups are never
overwritten.

The scripts use `.env.production` and `docker-compose.production.yml` by
default. A restore drill against a dedicated recovery stack can select other
absolute or repository-relative files without copying credentials:

```sh
DATE_PLANNER_PROD_ENV_FILE=/secure/recovery.env \
DATE_PLANNER_PROD_COMPOSE_FILE=docker-compose.recovery.yml \
deploy/scripts/backup-postgres.sh /srv/date-planner/backups
```

Do not place a populated environment file in Git or in the backup directory.

### Verify a restore

Every backup is incomplete operationally until an actual restore has succeeded:

```sh
deploy/scripts/verify-postgres-restore.sh \
  /srv/date-planner/backups/date-planner-postgres-YYYYmmddTHHMMSSZ.dump
```

The verification command:

1. compares the archive with its `.sha256` file;
2. verifies that `pg_restore` can read the archive catalog;
3. creates a uniquely named database from `template0`;
4. restores the archive in a single transaction with errors treated as fatal;
5. runs `python manage.py migrate --check` using the restored database;
6. checks required Django/application tables, lifecycle invariants, confirmed
   plan timestamps, and PostgreSQL constraint validation;
7. drops only the generated verification database, including after a failed
   check or an interrupted run.

The script never accepts a database name and cannot use the configured
production database as its restore target. A logical restore on the production
PostgreSQL server still consumes CPU, disk space, and I/O, so routine drills
should run against a separate recovery host or stack with the same PostgreSQL
major version. If cleanup reports a warning, remove the printed
`date_planner_restore_verify_*` database after confirming that no verification
process is active.

### Schedule, retention, and off-host storage

The initial operating policy is:

- create a backup at least every 24 hours;
- retain 7 daily, 4 weekly, and 6 monthly recovery points;
- copy the dump and checksum off the Docker host immediately;
- encrypt backups in transit and at rest, with the decryption key stored
  separately from both the database host and the backup objects;
- enable object versioning or immutability so a compromised host cannot rewrite
  all recovery points;
- verify the newest backup automatically after every run and perform a
  supervised clean-host restore drill at least monthly.

This cadence gives a baseline RPO of 24 hours. The initial RTO target is four
hours after replacement infrastructure and credentials are available. Measure
the real dump, transfer, restore, migration check, and smoke-test durations;
tighten the schedule or add PostgreSQL physical/WAL archiving if the measured
RPO/RTO is not acceptable.

Monitor backup age, command exit status, archive size, checksum verification,
off-host upload status, and restore-drill status. An alert is required when a
daily recovery point is late or any stage fails. Do not log database passwords,
environment-file contents, archive contents, invitation data, or management
capabilities.

### Disaster recovery

The verification script deliberately cannot replace production data. For a real
recovery:

1. stop application writes and record the incident start time;
2. preserve the failed volume or take a provider snapshot before changing it;
3. provision an empty PostgreSQL 18 database/volume on replacement
   infrastructure;
4. verify the selected dump and checksum, then run the isolated restore drill
   against that recovery stack;
5. create the intended empty application database from `template0` and restore
   the same archive with `pg_restore --exit-on-error --single-transaction
   --no-owner --no-privileges`;
6. run `python manage.py migrate --check` and the deployment checks before
   allowing traffic;
7. start the application, run the full HTTPS production smoke scenario, and
   only then switch DNS or the reverse proxy;
8. record the recovered backup timestamp, achieved RPO/RTO, checks performed,
   and approval to reopen traffic.

Never restore over the only copy of a damaged database. Prefer a new volume so
rollback remains possible.

### Credentials and sensitive data

The dump contains invitation names, messages, planning details, and hashed
management capabilities. Treat the dump and checksum as production-sensitive
data, grant least-privilege access, audit downloads, and apply the same deletion
policy to expired backup objects.

For the official PostgreSQL image, `POSTGRES_ADMIN_PASSWORD`,
`POSTGRES_ADMIN_USER`, `POSTGRES_APP_PASSWORD`, `POSTGRES_APP_USER`, and
`POSTGRES_DB` initialize only an empty data directory. Editing
`.env.production` does not rotate a role password in an existing volume. The
admin role is reserved for initialization and recovery; Django uses the
non-superuser application role. Rotate each role inside PostgreSQL, update the
matching deployment secret in the same maintenance window, restart dependent
services, and verify both a new backup and restore. Back up deployment
configuration and secret-recovery material separately from the database
archive; never commit either to the repository. `pg_dump` archives one database,
not cluster-wide roles or role passwords, so provision the admin and application
roles separately before restoring onto replacement infrastructure.
