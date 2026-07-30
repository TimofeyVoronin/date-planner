"""Privacy-preserving structured log formatting for production output."""

import json
import logging
import re
import traceback
from datetime import UTC, datetime

_BEARER_PATTERN = re.compile(r"(?i)\bbearer\s+[a-z0-9._~+/=-]+")
_SENSITIVE_PARAMETER_PATTERN = re.compile(
    r"(?i)(?P<name>token|secret|password|authorization|key)=(?P<value>[^&\s]+)"
)
_EMAIL_PATTERN = re.compile(r"(?i)\b[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-z0-9.-]+\.[a-z]{2,}\b")
_UUID_PATTERN = re.compile(
    r"(?i)\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b"
)
_LONG_CREDENTIAL_PATTERN = re.compile(r"(?<![a-zA-Z0-9_-])[a-zA-Z0-9_-]{32,}(?![a-zA-Z0-9_-])")
_REQUEST_LOGGER_PREFIXES = ("django.request", "django.server", "django.security")


def redact_sensitive_log_data(value: str) -> str:
    """Remove credentials and common identifiers without logging their values."""
    value = _BEARER_PATTERN.sub("Bearer [redacted]", value)
    value = _SENSITIVE_PARAMETER_PATTERN.sub(r"\g<name>=[redacted]", value)
    value = _EMAIL_PATTERN.sub("[email]", value)
    value = _UUID_PATTERN.sub("[uuid]", value)
    return _LONG_CREDENTIAL_PATTERN.sub("[credential]", value)


class PrivacySafeJsonFormatter(logging.Formatter):
    """Emit a fixed JSON schema without request targets or exception values."""

    def format(self, record: logging.LogRecord) -> str:
        if record.name.startswith(_REQUEST_LOGGER_PREFIXES):
            message = "Framework request or security event."
        else:
            message = redact_sensitive_log_data(record.getMessage())

        payload: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": message,
        }
        status_code = getattr(record, "status_code", None)
        if isinstance(status_code, int):
            payload["status_code"] = status_code
        if record.exc_info and record.exc_info[0] is not None:
            payload["exception"] = {
                "type": record.exc_info[0].__name__,
                "frames": [
                    {
                        "file": frame.filename,
                        "line": frame.lineno,
                        "function": frame.name,
                    }
                    for frame in traceback.extract_tb(record.exc_info[2])
                ],
            }
        return json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
