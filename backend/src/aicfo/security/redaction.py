"""Logging redaction: a safety net that masks secrets and identifiers.

Code must still never log personal data on purpose. This filter catches
mistakes: PAN numbers, JWT-style tokens (Dhan access tokens are JWTs),
email addresses, Indian mobile numbers and long opaque secrets.
"""

from __future__ import annotations

import logging
import re

_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+"), "[REDACTED_JWT]"),
    (re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b"), "[REDACTED_PAN]"),
    (re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"), "[REDACTED_EMAIL]"),
    (re.compile(r"(?<!\d)(?:\+?91[\s-]?)?[6-9]\d{9}(?!\d)"), "[REDACTED_PHONE]"),
    (re.compile(r"\b[A-Za-z0-9_\-+/=]{40,}\b"), "[REDACTED_SECRET]"),
)


def redact(text: str) -> str:
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return text


class RedactingFilter(logging.Filter):
    """Rewrites each record's final message with sensitive values masked."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact(record.getMessage())
        record.args = None
        return True


def install(logger: logging.Logger | None = None) -> None:
    """Attach the filter to every handler of ``logger`` (default: root)."""
    target = logger or logging.getLogger()
    if not target.handlers:
        logging.basicConfig(level=logging.INFO)
    for handler in target.handlers:
        if not any(isinstance(f, RedactingFilter) for f in handler.filters):
            handler.addFilter(RedactingFilter())
