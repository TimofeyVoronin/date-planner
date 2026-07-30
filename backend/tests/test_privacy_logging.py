"""Tests for privacy-preserving production log output."""

import json
import logging

from config.logging import PrivacySafeJsonFormatter, redact_sensitive_log_data


def test_redactor_removes_credentials_and_identifiers() -> None:
    sentinel_token = "sensitive-management-token-value-1234567890"
    message = (
        "Bearer secret-auth-value "
        "token=query-secret "
        "person@example.com "
        "164e8d5b-3062-4d7c-9250-04a284f3054e "
        f"{sentinel_token}"
    )

    redacted = redact_sensitive_log_data(message)

    for sensitive_value in (
        "secret-auth-value",
        "query-secret",
        "person@example.com",
        "164e8d5b-3062-4d7c-9250-04a284f3054e",
        sentinel_token,
    ):
        assert sensitive_value not in redacted
    assert "Bearer [redacted]" in redacted
    assert "token=[redacted]" in redacted
    assert "[email]" in redacted
    assert "[uuid]" in redacted
    assert "[credential]" in redacted


def test_formatter_omits_exception_messages_and_emits_json() -> None:
    formatter = PrivacySafeJsonFormatter()
    sentinel = "exception-secret-token-value-1234567890"

    try:
        raise ValueError(f"request failed for token={sentinel}")
    except ValueError:
        record = logging.LogRecord(
            name="date_planner",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="Unhandled failure",
            args=(),
            exc_info=__import__("sys").exc_info(),
        )

    output = formatter.format(record)
    payload = json.loads(output)

    assert sentinel not in output
    assert payload["level"] == "ERROR"
    assert payload["logger"] == "date_planner"
    assert payload["message"] == "Unhandled failure"
    assert payload["exception"]["type"] == "ValueError"
    assert payload["exception"]["frames"]


def test_formatter_suppresses_framework_request_targets() -> None:
    formatter = PrivacySafeJsonFormatter()
    sentinel_path = "/api/v1/invitations/164e8d5b-3062-4d7c-9250-04a284f3054e/"
    record = logging.LogRecord(
        name="django.request",
        level=logging.WARNING,
        pathname=__file__,
        lineno=1,
        msg="Not Found: %s?token=secret-value",
        args=(sentinel_path,),
        exc_info=None,
    )
    record.status_code = 404

    output = formatter.format(record)
    payload = json.loads(output)

    assert sentinel_path not in output
    assert "secret-value" not in output
    assert payload["message"] == "Framework request or security event."
    assert payload["status_code"] == 404
