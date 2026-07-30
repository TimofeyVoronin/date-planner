"""Verify that the production application role has no administrative powers."""

from django.core.management.base import BaseCommand, CommandError
from django.db import connection


class Command(BaseCommand):
    """Fail a release when Django connects with a privileged PostgreSQL role."""

    help = "Verify that Django's PostgreSQL role is not a superuser or cluster administrator."

    def handle(self, *args: object, **options: object) -> None:
        del args, options
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication
                FROM pg_roles
                WHERE rolname = current_user
                """
            )
            role_flags = cursor.fetchone()

        if role_flags is None or any(role_flags):
            raise CommandError(
                "Django must connect with a non-superuser PostgreSQL role "
                "without CREATEDB, CREATEROLE, or REPLICATION."
            )

        self.stdout.write(self.style.SUCCESS("Production database role is restricted."))
