"""Logging redaction: a safety net that masks secrets and identifiers.

Code must still never log personal data on purpose. This filter catches
mistakes: PAN numbers, JWT-style tokens (Dhan access tokens are JWTs),
email addresses, Indian mobile numbers and long opaque secrets.
"""

from __future__ import annotations

import logging
import re

# What to mask, in order: JWT tokens, PAN numbers, emails, Indian mobile numbers, long secrets.
_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+"), "[REDACTED_JWT]"),
    (re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b"), "[REDACTED_PAN]"),
    (re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"), "[REDACTED_EMAIL]"),
    (re.compile(r"(?<!\d)(?:\+?91[\s-]?)?[6-9]\d{9}(?!\d)"), "[REDACTED_PHONE]"),
    (re.compile(r"\b[A-Za-z0-9_\-+/=]{40,}\b"), "[REDACTED_SECRET]"),
)


# Return the text with sensitive values masked.
def redact(text: str) -> str:
    # Apply each pattern.
    for pattern, replacement in _PATTERNS:
        # Replace matches.
        text = pattern.sub(replacement, text)
    # Masked text.
    return text


# A logging filter that masks every log message.
class RedactingFilter(logging.Filter):
    """Rewrites each record's final message with sensitive values masked."""

    # Called for each log record.
    def filter(self, record: logging.LogRecord) -> bool:
        # Mask the final message.
        record.msg = redact(record.getMessage())
        # The message is already formatted.
        record.args = None
        # Keep the record.
        return True


# Attach the filter to the logger's handlers.
def install(logger: logging.Logger | None = None) -> None:
    """Attach the filter to every handler of ``logger`` (default: root)."""
    # The root logger by default.
    target = logger or logging.getLogger()
    # Make sure there is a handler to filter.
    if not target.handlers:
        # Default console logging.
        logging.basicConfig(level=logging.INFO)
    # Each handler.
    for handler in target.handlers:
        # Do not add the filter twice.
        if not any(isinstance(f, RedactingFilter) for f in handler.filters):
            # Mask everything that handler writes.
            handler.addFilter(RedactingFilter())
