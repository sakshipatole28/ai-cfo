"""Hash-chained audit log: each entry's hash covers the previous one, so edits are detectable."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from aicfo.db.models import AuditEvent

# The "previous hash" of the very first entry.
GENESIS = "0" * 64
# Time zero, for turning timestamps into integers.
_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


# SHA-256 of text, as hex.
def _sha(text: str) -> str:
    # Hash it.
    return hashlib.sha256(text.encode()).hexdigest()


# A timestamp as whole microseconds (SQLite returns naive datetimes; we always write UTC).
def _micros(at: datetime) -> int:
    # SQLite returns naive datetimes; everything is written in UTC.
    # Treat naive times as UTC.
    aware = at if at.tzinfo else at.replace(tzinfo=UTC)
    # Microseconds since 1970.
    return (aware - _EPOCH) // timedelta(microseconds=1)


# The hash of an entry: covers its content AND the previous entry's hash.
def _hash(e: AuditEvent) -> str:
    # Everything that must not change.
    fields = [
        e.prev_hash,
        e.tenant_id,
        str(_micros(e.at)),
        e.actor,
        e.action,
        e.object_type,
        e.object_id,
        e.details_hash,
    ]
    # Join and hash.
    return _sha("|".join(fields))


# Add an entry to the chain.
def append(
    session: Session,
    tenant_id: str,
    actor: str,
    action: str,
    object_type: str,
    object_id: str,
    details: dict[str, Any] | None = None,
) -> AuditEvent:
    """Callers pass IDs, counts and statuses only. Details are stored as a hash, not as text."""
    # The newest entry (locked, so two writers cannot fork the chain).
    last = session.scalars(
        select(AuditEvent).order_by(AuditEvent.seq.desc()).limit(1).with_for_update()
    ).first()
    # The new entry; details are stored only as a hash.
    e = AuditEvent(
        tenant_id=tenant_id,
        at=datetime.now(UTC),
        actor=actor,
        action=action,
        object_type=object_type,
        object_id=object_id,
        details_hash=_sha(json.dumps(details or {}, sort_keys=True, default=str)),
        prev_hash=last.hash if last else GENESIS,
    )
    # Seal it: the hash links it to the one before.
    e.hash = _hash(e)
    # Queue it.
    session.add(e)
    # Write so it has a sequence number.
    session.flush()
    # The new entry.
    return e


# Walk the whole chain and recompute every hash.
def verify(session: Session) -> tuple[bool, int]:
    """(chain intact, number of events). Breaks on any edited, deleted or reordered entry."""
    # Start from the genesis value.
    prev, n = GENESIS, 0
    # Entries in order.
    for e in session.scalars(select(AuditEvent).order_by(AuditEvent.seq)):
        # Broken link or edited content: the chain is not intact.
        if e.prev_hash != prev or _hash(e) != e.hash:
            # Report where it broke.
            return False, n
        # Move on.
        prev, n = e.hash, n + 1
    # Every entry checked out.
    return True, n
