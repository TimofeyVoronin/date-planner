"""Tests for the production PostgreSQL role verification command."""

from unittest.mock import MagicMock

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.common.management.commands import verify_database_role


def database_connection_with_flags(flags: tuple[bool, bool, bool, bool]) -> MagicMock:
    """Create a cursor context manager returning PostgreSQL role flags."""
    cursor = MagicMock()
    cursor.fetchone.return_value = flags
    cursor_context = MagicMock()
    cursor_context.__enter__.return_value = cursor
    connection = MagicMock()
    connection.cursor.return_value = cursor_context
    return connection


def test_restricted_application_role_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    connection = database_connection_with_flags((False, False, False, False))
    monkeypatch.setattr(verify_database_role, "connection", connection)

    call_command("verify_database_role")

    connection.cursor.assert_called_once_with()


@pytest.mark.parametrize(
    "flags",
    [
        (True, False, False, False),
        (False, True, False, False),
        (False, False, True, False),
        (False, False, False, True),
    ],
)
def test_privileged_application_role_blocks_release(
    flags: tuple[bool, bool, bool, bool],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = database_connection_with_flags(flags)
    monkeypatch.setattr(verify_database_role, "connection", connection)

    with pytest.raises(CommandError, match="non-superuser PostgreSQL role"):
        call_command("verify_database_role")
