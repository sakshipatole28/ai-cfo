"""SQLAlchemy models: the synthetic-phase subset of plan §3.4.

No names, PAN, contacts or emails are stored: clients are pseudonymous references, and
identity stays in the advisor's browser vault (ADR-0003). Every tenant table carries
`tenant_id` so row-level security can be switched on without a schema change.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, ClassVar

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# JSON column type: JSONB on Postgres (indexable), plain JSON elsewhere.
JSONType = JSON().with_variant(JSONB(), "postgresql")
# Exact decimals for rupee amounts (never floats).
Money = Numeric(16, 2)


# A new random id.
def _id() -> str:
    # UUIDs, so ids reveal nothing and cannot be guessed.
    return str(uuid.uuid4())


# The current time, in UTC.
def _now() -> datetime:
    # Timezone-aware.
    return datetime.now(UTC)


# Parent of every table.
class Base(DeclarativeBase):
    # How Python types map to column types.
    type_annotation_map: ClassVar[dict[Any, Any]] = {
        dict[str, Any]: JSONType,
        list[Any]: JSONType,
        datetime: DateTime(timezone=True),
    }


# A firm (RIA or distributor). Everything else belongs to one.
class Tenant(Base):
    __tablename__ = "tenants"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    slug: Mapped[str] = mapped_column(String(64), unique=True)
    display_name: Mapped[str] = mapped_column(String(120))
    firm_type: Mapped[str] = mapped_column(String(16))  # RIA / MFD / BROKER_WL
    registration: Mapped[str | None] = mapped_column(String(32))  # SEBI RIA or AMFI ARN number
    # The firm's data key, wrapped by the key-encryption key (envelope encryption). Seals TOTP
    # secrets today; client fields later. Destroying it crypto-shreds the firm's sealed data.
    wrapped_data_key: Mapped[str | None] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(default=_now)


# A firm employee who signs in.
class User(Base):
    """A firm employee who signs in. Staff details are needed to sign in; client identity is not
    stored here (ADR-0003). Emails are never logged or written to the audit log."""

    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)  # login name, lower-cased
    name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(16))  # Owner / Admin / Adviser / Analyst / Compliance
    # pending_mfa (authenticator not confirmed yet) / active / suspended
    status: Mapped[str] = mapped_column(String(16), default="pending_mfa")
    password_hash: Mapped[str] = mapped_column(String(256))  # scrypt, never the password
    totp_sealed: Mapped[str] = mapped_column(String(256))  # TOTP secret sealed with the firm key
    created_at: Mapped[datetime] = mapped_column(default=_now)
    last_login_at: Mapped[datetime | None]


# Access granted by an Owner or Admin: one email, one role, one-time code.
class Invite(Base):
    """Access granted by an Owner or Admin: a one-time code for one email and one role."""

    __tablename__ = "invites"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    email: Mapped[str] = mapped_column(String(254))
    role: Mapped[str] = mapped_column(String(16))
    code_hash: Mapped[str] = mapped_column(String(64), unique=True)  # SHA-256 of the code only
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    expires_at: Mapped[datetime]
    accepted_at: Mapped[datetime | None]
    revoked: Mapped[bool] = mapped_column(default=False)


# A client, identified only by a pseudonymous reference (no name or PAN).
class Client(Base):
    __tablename__ = "clients"
    __table_args__ = (UniqueConstraint("tenant_id", "ref"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    ref: Mapped[str] = mapped_column(String(64))  # pseudonymous reference used by the console
    risk: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16), default="active")
    created_at: Mapped[datetime] = mapped_column(default=_now)


# A client's portfolio computed on one day.
class Snapshot(Base):
    __tablename__ = "snapshots"
    __table_args__ = (UniqueConstraint("client_id", "inputs_hash"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    client_id: Mapped[str] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"))
    as_of: Mapped[str] = mapped_column(String(10))
    engine_version: Mapped[str] = mapped_column(String(32))
    inputs_hash: Mapped[str] = mapped_column(String(64))
    total: Mapped[Decimal] = mapped_column(Money)
    allocation_pct: Mapped[dict[str, Any]]
    drift: Mapped[dict[str, Any]]
    look_through_pct: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    created_at: Mapped[datetime] = mapped_column(default=_now)
    positions: Mapped[list[Position]] = relationship(
        back_populates="snapshot", cascade="all, delete-orphan"
    )


# One holding inside a snapshot.
class Position(Base):
    __tablename__ = "positions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("snapshots.id", ondelete="CASCADE"), index=True
    )
    ref: Mapped[str] = mapped_column(String(64))
    kind: Mapped[str] = mapped_column(String(16))
    name: Mapped[str] = mapped_column(String(160))  # security name (public data), not a person
    asset_class: Mapped[str] = mapped_column(String(16))
    source: Mapped[str] = mapped_column(String(32))
    units: Mapped[Decimal] = mapped_column(Numeric(20, 4))
    value: Mapped[Decimal] = mapped_column(Money)
    snapshot: Mapped[Snapshot] = relationship(back_populates="positions")


# One run of the agent graph, with its model, timing and full trace.
class ReviewRun(Base):
    """One LangGraph review run (plan: `agent_runs`)."""

    __tablename__ = "review_runs"
    __table_args__ = (Index("ix_review_runs_client_created", "client_id", "created_at"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    client_id: Mapped[str] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"))
    snapshot_id: Mapped[str | None] = mapped_column(ForeignKey("snapshots.id", ondelete="SET NULL"))
    profile: Mapped[str] = mapped_column(String(8))
    model: Mapped[str] = mapped_column(String(160))
    trigger: Mapped[str] = mapped_column(String(16))  # manual / schedule / api
    latency_ms: Mapped[int]
    kept: Mapped[int]
    dropped: Mapped[int]
    trace: Mapped[list[Any]]
    created_at: Mapped[datetime] = mapped_column(default=_now)
    findings: Mapped[list[Finding]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


# One drafted finding and the results of the compliance and verifier checks.
class Finding(Base):
    __tablename__ = "findings"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    run_id: Mapped[str] = mapped_column(
        ForeignKey("review_runs.id", ondelete="CASCADE"), index=True
    )
    ref: Mapped[str] = mapped_column(String(96))  # e.g. "<client>-overlap", same as the console
    kind: Mapped[str] = mapped_column(String(32))
    severity: Mapped[str] = mapped_column(String(8))
    impact: Mapped[Decimal] = mapped_column(Money)
    text: Mapped[str]  # uses the {client} placeholder; the name is filled in the browser
    author: Mapped[str] = mapped_column(String(16))
    evidence_ids: Mapped[list[Any]]
    citations: Mapped[list[Any]]
    compliance: Mapped[dict[str, Any]]
    verifier: Mapped[dict[str, Any]]
    # draft / dropped (by a guard) / accepted / dismissed / snoozed (by the advisor)
    status: Mapped[str] = mapped_column(String(16))
    run: Mapped[ReviewRun] = relationship(back_populates="findings")


# An adviser's approval of a client's review.
class Review(Base):
    """An advisor's approval of a client's review."""

    __tablename__ = "reviews"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    client_id: Mapped[str] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), index=True)
    run_id: Mapped[str | None] = mapped_column(ForeignKey("review_runs.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(16), default="approved")
    approved_by: Mapped[str] = mapped_column(String(64))  # member id, never an email
    approved_at: Mapped[datetime] = mapped_column(default=_now)
    decisions: Mapped[dict[str, Any]]
    source: Mapped[str] = mapped_column(String(16))  # console / api


# The append-only, hash-chained audit log (ids and hashes only).
class AuditEvent(Base):
    """Append-only, hash-chained audit log. IDs and hashes only, never personal data."""

    __tablename__ = "audit_log"
    seq: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(36), index=True)
    at: Mapped[datetime] = mapped_column(default=_now)
    actor: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(64))
    object_type: Mapped[str] = mapped_column(String(32))
    object_id: Mapped[str] = mapped_column(String(96))
    details_hash: Mapped[str] = mapped_column(String(64))
    prev_hash: Mapped[str] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64), unique=True)
