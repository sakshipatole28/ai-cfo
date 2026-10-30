"""Outbound events for n8n. Payloads carry IDs, counts and statuses only: no names, amounts or text.

The webhook body is signed with HMAC-SHA256 (`X-AICFO-Signature: sha256=<hex>`) so the
n8n workflow can reject forged calls.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from datetime import UTC, datetime
from functools import lru_cache
from typing import Protocol

import httpx

from aicfo.config import get_settings

# Module logger (never logs payloads).
log = logging.getLogger(__name__)
# Event data: only ids, counts and statuses.
Payload = dict[str, str | int | None]


# Anything that can receive events: n8n, a test double, nothing.
class EventSink(Protocol):
    # Send one event.
    def emit(self, event: str, payload: Payload) -> None: ...


# Used when no n8n is configured; keeps events in memory (handy in tests).
class NullSink:
    # Start empty.
    def __init__(self) -> None:
        # Events received.
        self.events: list[tuple[str, Payload]] = []

    # Remember the event.
    def emit(self, event: str, payload: Payload) -> None:
        # Store it.
        self.events.append((event, payload))


# Posts events to an n8n webhook, signed so n8n can verify they came from us.
class WebhookSink:
    # Where to send, the shared secret and a short timeout.
    def __init__(self, url: str, secret: str | None = None, timeout: float = 5.0) -> None:
        # n8n webhook address.
        self.url = url
        # HMAC key (as bytes), or None to send unsigned.
        self._secret = secret.encode() if secret else None
        # Never hang the API on n8n.
        self._timeout = timeout

    # Build, sign and send the event.
    def emit(self, event: str, payload: Payload) -> None:
        # Stable JSON: event name, time and data.
        body = json.dumps(
            {"event": event, "at": datetime.now(UTC).isoformat(), "data": payload},
            sort_keys=True,
        ).encode()
        # JSON content type.
        headers = {"Content-Type": "application/json"}
        # Sign when a secret is configured.
        if self._secret:
            # HMAC-SHA256 of the exact bytes being sent.
            sig = hmac.new(self._secret, body, hashlib.sha256).hexdigest()
            # n8n recomputes this and rejects mismatches.
            headers["X-AICFO-Signature"] = f"sha256={sig}"
        # Delivery is best effort.
        try:
            # Send it.
            httpx.post(self.url, content=body, headers=headers, timeout=self._timeout)
        # n8n being down must never break the request that caused the event.
        except httpx.HTTPError as exc:  # automation must never break the request that caused it
            # Log the event name and error type only.
            log.warning("event %s not delivered: %s", event, type(exc).__name__)


# Create the sink once.
@lru_cache
# The sink for the current settings.
def get_sink() -> EventSink:
    # Read settings.
    s = get_settings()
    # No n8n configured…
    if not s.n8n_webhook_url:
        # …so events go nowhere.
        return NullSink()
    # The signing secret, if set.
    secret = s.n8n_webhook_secret.get_secret_value() if s.n8n_webhook_secret else None
    # Send to n8n.
    return WebhookSink(s.n8n_webhook_url, secret)
