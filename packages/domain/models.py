from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def uuid4_str() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(UTC)


class TransactionType(StrEnum):
    sale = "sale"
    rent = "rent"


class SlotStatus(StrEnum):
    available = "available"
    booked = "booked"


class Agency(Base):
    __tablename__ = "agencies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4_str)
    name: Mapped[str] = mapped_column(String(120))
    timezone: Mapped[str] = mapped_column(String(64), default="Europe/Paris")
    default_language: Mapped[str] = mapped_column(String(16), default="en")


class Property(Base):
    __tablename__ = "properties"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4_str)
    agency_id: Mapped[str] = mapped_column(ForeignKey("agencies.id"), index=True)
    external_ref: Mapped[str] = mapped_column(String(40), unique=True)
    transaction_type: Mapped[TransactionType] = mapped_column(Enum(TransactionType))
    property_type: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text)
    address_display: Mapped[str] = mapped_column(String(180))
    city: Mapped[str] = mapped_column(String(80), index=True)
    postal_code: Mapped[str] = mapped_column(String(16))
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    bedrooms: Mapped[int] = mapped_column(Integer)
    bathrooms: Mapped[int] = mapped_column(Integer)
    area_m2: Mapped[int] = mapped_column(Integer)
    amenities: Mapped[str] = mapped_column(Text, default="")
    available_from: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    slots: Mapped[list[ViewingSlot]] = relationship(back_populates="property")


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4_str)
    agency_id: Mapped[str] = mapped_column(ForeignKey("agencies.id"), index=True)
    name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    phone_e164: Mapped[str | None] = mapped_column(String(24), nullable=True)
    email: Mapped[str | None] = mapped_column(String(254), nullable=True)
    preferred_language: Mapped[str] = mapped_column(String(16), default="en")
    contact_consent_status: Mapped[str] = mapped_column(String(20), default="unknown")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class LeadPreference(Base):
    __tablename__ = "lead_preferences"

    lead_id: Mapped[str] = mapped_column(ForeignKey("leads.id"), primary_key=True)
    city: Mapped[str | None] = mapped_column(String(80), nullable=True)
    transaction_type: Mapped[TransactionType | None] = mapped_column(
        Enum(TransactionType), nullable=True
    )
    budget_max: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    bedrooms_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class ViewingSlot(Base):
    __tablename__ = "viewing_slots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4_str)
    property_id: Mapped[str] = mapped_column(ForeignKey("properties.id"), index=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[SlotStatus] = mapped_column(Enum(SlotStatus), default=SlotStatus.available)

    property: Mapped[Property] = relationship(back_populates="slots")


class Viewing(Base):
    __tablename__ = "viewings"
    __table_args__ = (
        UniqueConstraint("slot_id", name="uq_viewings_slot_id"),
        UniqueConstraint("idempotency_key", name="uq_viewings_idempotency_key"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4_str)
    slot_id: Mapped[str] = mapped_column(ForeignKey("viewing_slots.id"), index=True)
    lead_id: Mapped[str] = mapped_column(ForeignKey("leads.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="confirmed")
    confirmation_channel: Mapped[str] = mapped_column(String(20), default="browser")
    confirmation_email_status: Mapped[str] = mapped_column(String(20), default="pending")
    confirmation_email_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    idempotency_key: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CallSession(Base):
    __tablename__ = "calls"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4_str)
    session_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    agency_id: Mapped[str] = mapped_column(ForeignKey("agencies.id"), index=True)
    lead_id: Mapped[str] = mapped_column(ForeignKey("leads.id"), index=True)
    booking_id: Mapped[str | None] = mapped_column(
        ForeignKey("viewings.id"), nullable=True, unique=True
    )
    mode: Mapped[str] = mapped_column(String(20), default="browser_text")
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)
    model_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    disposition: Mapped[str | None] = mapped_column(String(40), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CallTurn(Base):
    __tablename__ = "call_turns"
    __table_args__ = (UniqueConstraint("call_id", "sequence", name="uq_call_turn_sequence"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4_str)
    call_id: Mapped[str] = mapped_column(ForeignKey("calls.id"), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    speaker: Mapped[str] = mapped_column(String(20))
    text: Mapped[str] = mapped_column(Text)
    interrupted: Mapped[bool] = mapped_column(Boolean, default=False)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ToolExecution(Base):
    __tablename__ = "tool_executions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4_str)
    call_id: Mapped[str] = mapped_column(ForeignKey("calls.id"), index=True)
    tool_name: Mapped[str] = mapped_column(String(80))
    arguments_redacted: Mapped[str] = mapped_column(Text)
    result_redacted: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20))
    latency_ms: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PropertyMatch(Base):
    __tablename__ = "property_matches"
    __table_args__ = (
        UniqueConstraint("call_id", "property_id", name="uq_property_match_call_property"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4_str)
    call_id: Mapped[str] = mapped_column(ForeignKey("calls.id"), index=True)
    property_id: Mapped[str] = mapped_column(ForeignKey("properties.id"), index=True)
    rank: Mapped[int] = mapped_column(Integer)
    presented_to_caller: Mapped[bool] = mapped_column(Boolean, default=True)
