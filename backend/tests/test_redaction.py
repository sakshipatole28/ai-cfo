import logging

import pytest

from aicfo.security.redaction import RedactingFilter, redact

# Synthetic values only. None of these belong to a real person.
# Assembled at runtime so secret scanners do not flag a literal token.
FAKE_JWT = ".".join(
    ["eyJ" + "hbGciOiJIUzUxMiJ9", "eyJ" + "zdWIiOiJ0ZXN0In0", "c2lnbmF0dXJlLXRlc3Q"]
)


@pytest.mark.parametrize(
    ("raw", "must_not_contain", "marker"),
    [
        (f"token={FAKE_JWT}", FAKE_JWT, "[REDACTED_JWT]"),
        ("pan ABCDE1234F matched", "ABCDE1234F", "[REDACTED_PAN]"),
        ("mail test.user+x@example.com", "test.user+x@example.com", "[REDACTED_EMAIL]"),
        ("call +91 9876543210 now", "9876543210", "[REDACTED_PHONE]"),
        ("secret " + "A" * 48, "A" * 48, "[REDACTED_SECRET]"),
    ],
)
def test_redact_masks_sensitive_values(raw: str, must_not_contain: str, marker: str) -> None:
    out = redact(raw)
    assert must_not_contain not in out
    assert marker in out


def test_redact_keeps_ordinary_text_and_isins() -> None:
    text = "synced 12 holdings incl. INE009A01021 in 340 ms"
    assert redact(text) == text


def test_filter_redacts_formatted_args(caplog: pytest.LogCaptureFixture) -> None:
    logger = logging.getLogger("test.redaction")
    logger.addFilter(RedactingFilter())
    with caplog.at_level(logging.INFO, logger="test.redaction"):
        logger.info("client pan=%s token=%s", "ABCDE1234F", FAKE_JWT)
    assert "ABCDE1234F" not in caplog.text
    assert FAKE_JWT not in caplog.text
