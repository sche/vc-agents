"""
SQLAlchemy models for VC Agents database.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all models."""

    type_annotation_map = {
        dict[str, Any]: JSONB,
        list[str]: JSONB,
        list[dict]: JSONB,
    }


class Organization(Base):
    """Organizations: VCs, startups, accelerators."""

    __tablename__ = "orgs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    website: Mapped[str | None] = mapped_column(String(1000))
    description: Mapped[str | None] = mapped_column(Text)
    focus: Mapped[list[str] | None] = mapped_column(JSONB)
    location: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    # Metadata
    sources: Mapped[list[dict]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'")
    )
    socials: Mapped[dict[str, Any]] = mapped_column(
        JSONB, server_default=text("'{}'")
    )

    # Deduplication
    uniq_key: Mapped[str | None] = mapped_column(String(255), unique=True)

    # Audit
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text('NOW()')
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text('NOW()')
    )

    # Relationships
    deals: Mapped[list["Deal"]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )
    roles: Mapped[list["RoleEmployment"]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint(
            "kind IN ('vc', 'startup', 'accelerator', 'other')",
            name="orgs_kind_check",
        ),
        UniqueConstraint("name", "kind", name="orgs_name_kind_key"),
    )

    def __repr__(self) -> str:
        return f"<Organization(id={self.id}, name='{self.name}', kind='{self.kind}')>"


class Deal(Base):
    """Funding rounds with normalized amounts."""

    __tablename__ = "deals"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Deal details
    round: Mapped[str | None] = mapped_column(String(100), index=True)
    amount_eur: Mapped[float | None] = mapped_column(Numeric(15, 2))
    amount_original: Mapped[float | None] = mapped_column(Numeric(15, 2))
    currency_original: Mapped[str | None] = mapped_column(String(10))

    announced_on: Mapped[datetime | None] = mapped_column(Date, index=True)
    investors: Mapped[list[str]] = mapped_column(
        JSONB, server_default=text("'[]'")
    )

    # Source tracking
    source: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    # Idempotency
    uniq_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)

    # Audit
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text('NOW()')
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text('NOW()')
    )

    # Relationships
    organization: Mapped["Organization"] = relationship(back_populates="deals")

    def __repr__(self) -> str:
        return (
            f"<Deal(id={self.id}, org_id={self.org_id}, "
            f"round='{self.round}', amount_eur={self.amount_eur})>"
        )


class Person(Base):
    """Individual contacts (VC partners, team members)."""

    __tablename__ = "people"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Identity
    full_name: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    email: Mapped[str | None] = mapped_column(String(255), index=True)

    # Socials
    socials: Mapped[dict[str, Any]] = mapped_column(
        JSONB, server_default=text("'{}'")
    )
    telegram_handle: Mapped[str | None] = mapped_column(String(100), index=True)
    telegram_confidence: Mapped[float | None] = mapped_column(Numeric(3, 2))

    # Provenance
    discovered_from: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    enrichment_history: Mapped[list[dict]] = mapped_column(
        JSONB, server_default=text("'[]'")
    )

    # Deduplication
    uniq_key: Mapped[str | None] = mapped_column(String(255))

    # Audit
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text('NOW()')
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text('NOW()')
    )

    # Relationships
    roles: Mapped[list["RoleEmployment"]] = relationship(
        back_populates="person", cascade="all, delete-orphan"
    )
    intros: Mapped[list["Intro"]] = relationship(
        back_populates="person", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Person(id={self.id}, full_name='{self.full_name}')>"


class RoleEmployment(Base):
    """Who works where (many-to-many with history)."""

    __tablename__ = "roles_employment"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    person_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("people.id", ondelete="CASCADE"), nullable=False, index=True
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Role details
    title: Mapped[str | None] = mapped_column(String(255))
    seniority: Mapped[str | None] = mapped_column(String(50), index=True)
    start_date: Mapped[datetime | None] = mapped_column(Date)
    end_date: Mapped[datetime | None] = mapped_column(Date)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    # Source
    evidence_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))

    # Audit
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text('NOW()')
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text('NOW()')
    )

    # Relationships
    person: Mapped["Person"] = relationship(back_populates="roles")
    organization: Mapped["Organization"] = relationship(back_populates="roles")

    __table_args__ = (
        UniqueConstraint(
            "person_id",
            "org_id",
            "title",
            "is_current",
            name="unique_person_org_role",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<RoleEmployment(id={self.id}, person_id={self.person_id}, "
            f"org_id={self.org_id}, title='{self.title}')>"
        )


class Evidence(Base):
    """Audit trail of all scraped/fetched data."""

    __tablename__ = "evidence"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # What was captured
    evidence_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    url: Mapped[str | None] = mapped_column(String(2000), index=True)
    selector: Mapped[str | None] = mapped_column(String(500))

    # Raw data
    raw_html: Mapped[str | None] = mapped_column(Text)
    raw_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    screenshot_url: Mapped[str | None] = mapped_column(String(1000))

    # Extraction metadata
    extracted_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    extraction_method: Mapped[str | None] = mapped_column(String(100))

    # Related entities
    org_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), index=True
    )
    person_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), index=True
    )

    # Audit
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text('NOW()')
    )

    def __repr__(self) -> str:
        return f"<Evidence(id={self.id}, type='{self.evidence_type}')>"


class Intro(Base):
    """Generated outreach messages."""

    __tablename__ = "intros"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    person_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("people.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Message content
    message: Mapped[str] = mapped_column(Text, nullable=False)
    subject: Mapped[str | None] = mapped_column(String(500))

    # Context used for generation
    context_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    # Delivery tracking
    status: Mapped[str] = mapped_column(
        String(50), server_default=text("'draft'"), index=True
    )
    sent_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    sent_via: Mapped[str | None] = mapped_column(String(50))

    # Quality/review
    reviewed_by: Mapped[str | None] = mapped_column(String(255))
    review_notes: Mapped[str | None] = mapped_column(Text)

    # Audit
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text('NOW()'), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text('NOW()')
    )

    # Relationships
    person: Mapped["Person"] = relationship(back_populates="intros")

    def __repr__(self) -> str:
        return f"<Intro(id={self.id}, person_id={self.person_id}, status='{self.status}')>"


class AgentRun(Base):
    """Execution logs for LangGraph agents."""

    __tablename__ = "agent_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Execution details
    agent_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    # Input/output
    input_params: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    output_summary: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    # Performance
    started_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text('NOW()'), index=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))

    # Error tracking
    error_message: Mapped[str | None] = mapped_column(Text)
    error_trace: Mapped[str | None] = mapped_column(Text)

    # LangGraph state snapshot
    langgraph_state: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    def __repr__(self) -> str:
        return (
            f"<AgentRun(id={self.id}, agent_name='{self.agent_name}', "
            f"status='{self.status}')>"
        )


class RateLimit(Base):
    """Simple rate limiting (alternative to Redis for MVP)."""

    __tablename__ = "rate_limits"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Rate limit key
    service: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    identifier: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    # Limits
    window_start: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, index=True
    )
    window_duration_seconds: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("3600")
    )
    request_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    max_requests: Mapped[int] = mapped_column(Integer, nullable=False)

    # Audit
    last_request_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text('NOW()')
    )

    __table_args__ = (
        UniqueConstraint(
            "service", "identifier", "window_start", name="unique_rate_limit"
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<RateLimit(service='{self.service}', "
            f"identifier='{self.identifier}', count={self.request_count})>"
        )
