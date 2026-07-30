#!/bin/sh
set -eu

# The official PostgreSQL image runs this file only while initializing an empty
# data directory. Values are read by psql from the environment so passwords do
# not appear in process arguments or command output.
psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" --set ON_ERROR_STOP=1 <<'SQL'
\getenv app_user POSTGRES_APP_USER
\getenv app_password POSTGRES_APP_PASSWORD
\getenv database_name POSTGRES_DB

CREATE ROLE :"app_user"
    LOGIN
    PASSWORD :'app_password'
    NOSUPERUSER
    NOCREATEDB
    NOCREATEROLE
    NOINHERIT
    NOREPLICATION;

ALTER DATABASE :"database_name" OWNER TO :"app_user";
\connect :"database_name"
ALTER SCHEMA public OWNER TO :"app_user";
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
SQL
